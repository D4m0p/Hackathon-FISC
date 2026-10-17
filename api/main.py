"""API HTTP del sistema. El frontend solo habla con esto.

Levantar:  .venv/bin/uvicorn api.main:app --reload --port 8010 --timeout-keep-alive 30
Documentación interactiva: http://localhost:8010/docs
"""
from __future__ import annotations

import os
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from contrato.modelos import (
    Asignacion, CasiCalifica, Curso, DatosPersonales, Desglose, EstadoVacante, Joven, PlanFormacion,
    Pesos, ResultadoAuditoria, ResultadoMatching, TipoCierre, Traslado, Traza, Vacante, Habilidad,
)
from orquestador import ErrorDeFlujo, HistoriaJoven, NoEncontrado, Orquestador, Simulacion
from agentes.perfil import ClienteLLM, cliente_desde_entorno
from agentes.perfil.rutas import crear_router as rutas_perfil
from orquestador.arranque import orquestador_desde_entorno
from orquestador.interfaces import es_oferta_incompleta, faltantes_de

from .limites import LimiteAnonimos, tope_desde_entorno
from .registro import RegistroPeticiones, error_inesperado
from .seguridad import Identidad, Rol, dependencias, nuevo_token, sin_permiso

MAX_TEXTO = 5000   # guardrail: ofertas y CVs más largos se rechazan antes de llegar al LLM


# ---------- cuerpos de petición y respuesta ----------

class OfertaTexto(BaseModel):
    texto: str = Field(min_length=10, max_length=MAX_TEXTO)
    empresa_id: str = Field(min_length=1, max_length=100)


class ResultadoPublicacion(BaseModel):
    vacante: Vacante
    auditoria: ResultadoAuditoria


class Motivo(BaseModel):
    motivo: str = Field(min_length=1, max_length=1000)


class RegistroJoven(BaseModel):
    joven: Joven
    datos: DatosPersonales | None = None


class RespuestaRegistro(BaseModel):
    joven: Joven
    token: str | None = None   # solo al registrarse por primera vez; guárdelo, no se vuelve a mostrar


class NuevaCredencial(BaseModel):
    rol: Rol
    sujeto: str | None = Field(default=None, max_length=100)


class TokenEmitido(BaseModel):
    token: str


class TarjetaVacante(BaseModel):
    vacante: Vacante
    desglose: Desglose


class TarjetaCandidato(BaseModel):
    """Lo que ve la empresa: sin nombre, género, edad ni contacto."""
    joven: Joven
    desglose: Desglose


def _anonimo(joven: Joven) -> Joven:
    """Para la empresa: habilidades y niveles, SIN la evidencia textual. La evidencia es una
    frase del CV o de la entrevista y puede traer nombre, cédula o teléfono."""
    return joven.model_copy(update={"habilidades": [h.model_copy(update={"evidencia": None})
                                                    for h in joven.habilidades]})


class Deslizamiento(BaseModel):
    actor: Literal["joven", "empresa"]
    joven_id: str
    vacante_id: str
    le_interesa: bool


class RespuestaDeslizamiento(BaseModel):
    interes_mutuo: bool


class Decision(BaseModel):
    aprobar: bool
    motivo: str = Field(default="", max_length=1000)


class CambioPesos(BaseModel):
    pesos: Pesos
    motivo: str = Field(min_length=1, max_length=1000)


class Liberacion(BaseModel):
    tipo: Literal["cancelacion_joven", "inasistencia", "retiro_empresa"]
    motivo: str = Field(min_length=1, max_length=1000)


class ResultadoLiberacion(BaseModel):
    liberada: Asignacion
    nuevas: list[Asignacion]   # propuestas de reemplazo, pendientes del orientador


class ResultadoCierre(BaseModel):
    vacante: Vacante
    afectadas: list[Asignacion]
    nuevas: list[Asignacion]


# ---------- construcción ----------

def crear_app(orq: Orquestador, cliente_llm: ClienteLLM | None = None,
              limite_anonimo_por_minuto: int | None = None) -> FastAPI:
    """`cliente_llm`: modelo para el agente Perfil. None = sin LLM (palabras clave).
    `limite_anonimo_por_minuto`: tope por IP sin token; None = variable LIMITE_ANONIMO_POR_MINUTO (30)."""
    app = FastAPI(title="Empleo joven — sistema de agentes", version="0.3")
    # Orden: el último que se agrega es el más externo (registro > CORS > límite).
    app.add_middleware(LimiteAnonimos, almacen=orq.almacen,
                       tope=limite_anonimo_por_minuto or tope_desde_entorno())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("ORIGENES_PERMITIDOS", "http://localhost:5173").split(","),
        allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(RegistroPeticiones)
    app.add_exception_handler(Exception, error_inesperado)
    opcional, requerida = dependencias(orq.almacen)
    # Agente Perfil: /perfil/preguntas, /perfil/cv y /perfil/entrevista (abiertos: el
    # joven todavía no tiene token; no guardan nada, solo proponen habilidades).
    app.include_router(rutas_perfil(orq, cliente=cliente_llm, usar_entorno=False))

    def solo_orientador(ident: Identidad = Depends(requerida)) -> Identidad:
        if not ident.es_orientador:
            raise sin_permiso("Solo el orientador puede hacer esto")
        return ident

    def exigir_joven(ident: Identidad, joven_id: str) -> None:
        if not ident.es_joven(joven_id):
            raise sin_permiso()

    def exigir_dueno_vacante(ident: Identidad, vacante_id: str) -> Vacante:
        v = orq._vacante(vacante_id)
        if not ident.es_empresa(v.empresa_id):
            raise sin_permiso()
        return v

    @app.exception_handler(NoEncontrado)
    async def _no_encontrado(_: Request, e: NoEncontrado):
        return JSONResponse(status_code=404, content={"detail": str(e)})

    @app.exception_handler(ErrorDeFlujo)
    async def _error_de_flujo(_: Request, e: ErrorDeFlujo):
        return JSONResponse(status_code=400, content={"detail": str(e)})

    # ----- públicos -----
    @app.get("/salud")
    def salud():
        if not orq.almacen.responde():
            return JSONResponse(status_code=503, content={"estado": "sin_base",
                                                          "detail": "La base de datos no responde"})
        return {"estado": "ok", "base": "ok",
                "mercado": type(orq.mercado).__name__, "auditor": type(orq.auditor).__name__,
                "perfil": type(cliente_llm).__name__ if cliente_llm else "palabras_clave",
                "notificador": type(orq.notificador).__name__}

    @app.get("/yo")
    def yo(ident: Identidad = Depends(requerida)) -> Identidad:
        return ident

    @app.get("/traslados")
    def listar_traslados() -> list[Traslado]:
        return orq.almacen.traslados()

    @app.get("/habilidades")
    def listar_habilidades() -> list[Habilidad]:
        return orq.almacen.listar(Habilidad)

    @app.get("/cursos")
    def listar_cursos() -> list[Curso]:
        return orq.almacen.listar(Curso)

    # ----- datos de referencia y credenciales (orientador) -----
    @app.post("/traslados", status_code=204)
    def cargar_traslados(traslados: list[Traslado], _: Identidad = Depends(solo_orientador)):
        orq.almacen.guardar_traslados(traslados)

    @app.post("/habilidades", status_code=204)
    def cargar_habilidades(habilidades: list[Habilidad], _: Identidad = Depends(solo_orientador)):
        for h in habilidades:
            orq.almacen.guardar(h)

    @app.post("/cursos", status_code=204)
    def cargar_cursos(cursos: list[Curso], _: Identidad = Depends(solo_orientador)):
        for c in cursos:
            orq.almacen.guardar(c)

    @app.post("/credenciales")
    def emitir_credencial(c: NuevaCredencial, _: Identidad = Depends(solo_orientador)) -> TokenEmitido:
        if c.rol != "orientador" and not c.sujeto:
            raise HTTPException(status_code=422, detail="Joven y empresa necesitan sujeto")
        token = nuevo_token()
        orq.almacen.guardar_credencial(token, c.rol, c.sujeto if c.rol != "orientador" else None)
        return TokenEmitido(token=token)

    # ----- empresas -----
    @app.post("/ofertas")
    def publicar_oferta(oferta: OfertaTexto, ident: Identidad = Depends(requerida)) -> ResultadoPublicacion:
        if not ident.es_empresa(oferta.empresa_id):
            raise sin_permiso("Solo puede publicar ofertas a nombre de su empresa")
        try:
            v, r = orq.publicar_oferta(oferta.texto, oferta.empresa_id)
        except NotImplementedError as e:
            raise HTTPException(status_code=501, detail=str(e))
        except Exception as e:
            if es_oferta_incompleta(e):   # 422 con la lista para que la empresa complete
                return JSONResponse(status_code=422,
                                    content={"detail": str(e), "faltantes": faltantes_de(e)})
            raise
        return ResultadoPublicacion(vacante=v, auditoria=r)

    @app.post("/vacantes")
    def publicar_vacante(vacante: Vacante, ident: Identidad = Depends(requerida)) -> ResultadoPublicacion:
        if not ident.es_empresa(vacante.empresa_id):
            raise sin_permiso("Solo puede publicar vacantes a nombre de su empresa")
        existente = orq.almacen.obtener(Vacante, vacante.id)
        if existente is not None and not ident.es_empresa(existente.empresa_id):
            raise sin_permiso("Ese id de vacante pertenece a otra empresa")
        v, r = orq.publicar_vacante(vacante)
        return ResultadoPublicacion(vacante=v, auditoria=r)

    @app.get("/vacantes")
    def listar_vacantes(estado: EstadoVacante | None = None,
                        ident: Identidad | None = Depends(opcional)) -> list[Vacante]:
        def visible(v: Vacante) -> bool:
            return v.estado == EstadoVacante.publicada or (ident is not None and ident.es_empresa(v.empresa_id))
        return [v for v in orq.almacen.listar(Vacante)
                if visible(v) and (estado is None or v.estado == estado)]

    @app.get("/vacantes/{vacante_id}")
    def obtener_vacante(vacante_id: str, ident: Identidad | None = Depends(opcional)) -> Vacante:
        v = orq._vacante(vacante_id)
        if v.estado != EstadoVacante.publicada and not (ident and ident.es_empresa(v.empresa_id)):
            raise NoEncontrado(f"No existe la vacante {vacante_id}")   # no se revela que existe
        return v

    @app.post("/vacantes/{vacante_id}/publicar-bloqueada")
    def publicar_bloqueada(vacante_id: str, cuerpo: Motivo, _: Identidad = Depends(solo_orientador)) -> Vacante:
        return orq.orientador_publicar_bloqueada(vacante_id, cuerpo.motivo)

    @app.get("/vacantes/{vacante_id}/tarjetas")
    def tarjetas_de_la_vacante(vacante_id: str, ident: Identidad = Depends(requerida)) -> list[TarjetaCandidato]:
        exigir_dueno_vacante(ident, vacante_id)
        return [TarjetaCandidato(joven=_anonimo(j), desglose=d) for j, d in orq.tarjetas_vacante(vacante_id)]

    @app.post("/vacantes/{vacante_id}/cerrar")
    def cerrar_vacante(vacante_id: str, cuerpo: Motivo, ident: Identidad = Depends(requerida)) -> ResultadoCierre:
        exigir_dueno_vacante(ident, vacante_id)
        vacante, afectadas, nuevas = orq.cerrar_vacante(vacante_id, cuerpo.motivo)
        return ResultadoCierre(vacante=vacante, afectadas=afectadas, nuevas=nuevas)

    # ----- jóvenes -----
    @app.post("/jovenes")
    def registrar_joven(registro: RegistroJoven,
                        ident: Identidad | None = Depends(opcional)) -> RespuestaRegistro:
        """Registro abierto para un joven NUEVO (devuelve su token). Para actualizar un
        perfil existente hace falta el token de ese joven o del orientador."""
        existe = orq.almacen.obtener(Joven, registro.joven.id) is not None
        if existe and not (ident and ident.es_joven(registro.joven.id)):
            raise sin_permiso("Ese joven ya está registrado")
        joven = orq.registrar_joven(registro.joven, registro.datos)
        token = None
        if not existe:
            token = nuevo_token()
            orq.almacen.guardar_credencial(token, "joven", joven.id)
        return RespuestaRegistro(joven=joven, token=token)

    @app.get("/jovenes")
    def listar_jovenes(_: Identidad = Depends(solo_orientador)) -> list[Joven]:
        return orq.almacen.listar(Joven)

    @app.get("/jovenes/{joven_id}")
    def obtener_joven(joven_id: str, ident: Identidad = Depends(requerida)) -> Joven:
        exigir_joven(ident, joven_id)
        return orq._joven(joven_id)

    @app.get("/jovenes/{joven_id}/tarjetas")
    def tarjetas_del_joven(joven_id: str, ident: Identidad = Depends(requerida)) -> list[TarjetaVacante]:
        exigir_joven(ident, joven_id)
        return [TarjetaVacante(vacante=v, desglose=d) for v, d in orq.tarjetas_joven(joven_id)]

    @app.get("/jovenes/{joven_id}/plan")
    def plan_de_formacion(joven_id: str, ident: Identidad = Depends(requerida)) -> PlanFormacion:
        exigir_joven(ident, joven_id)
        orq._joven(joven_id)
        plan = orq.plan_de(joven_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Este joven no tiene plan de formación")
        return plan

    @app.get("/planes")
    def listar_planes(_: Identidad = Depends(solo_orientador)) -> list[PlanFormacion]:
        """Todos los planes de formación de una vez (para la pestaña «Sin match»)."""
        return orq.almacen.listar(PlanFormacion)

    @app.get("/jovenes/{joven_id}/historia")
    def historia(joven_id: str, ident: Identidad = Depends(requerida)) -> HistoriaJoven:
        exigir_joven(ident, joven_id)
        return orq.historia(joven_id)

    @app.get("/jovenes/{joven_id}/casi-califica")
    def casi(joven_id: str, ident: Identidad = Depends(requerida)) -> list[CasiCalifica]:
        exigir_joven(ident, joven_id)
        return orq.casi_califica(joven_id)

    @app.post("/deslizar")
    def deslizar(d: Deslizamiento, ident: Identidad = Depends(requerida)) -> RespuestaDeslizamiento:
        if not ident.es_orientador:
            if ident.rol != d.actor:
                raise sin_permiso("Solo puede deslizar con su propio rol")
            if d.actor == "joven":
                exigir_joven(ident, d.joven_id)
            else:
                exigir_dueno_vacante(ident, d.vacante_id)
        return RespuestaDeslizamiento(
            interes_mutuo=orq.deslizar(d.actor, d.joven_id, d.vacante_id, d.le_interesa))

    # ----- matching y orientador -----
    @app.post("/matching")
    def ejecutar_matching(_: Identidad = Depends(solo_orientador)) -> ResultadoMatching:
        return orq.ejecutar_matching()

    @app.get("/asignaciones")
    def listar_asignaciones(estado: Literal["pendiente", "aprobada", "rechazada", "cerrada"] | None = None,
                            ident: Identidad = Depends(requerida)) -> list[Asignacion]:
        def estado_de(a: Asignacion) -> str:
            if not a.vigente:
                return "cerrada"
            return {None: "pendiente", True: "aprobada", False: "rechazada"}[a.aprobada]
        empresa_de = {v.id: v.empresa_id for v in orq.almacen.listar(Vacante)}

        def visible(a: Asignacion) -> bool:
            return ident.es_joven(a.joven_id) or ident.es_empresa(empresa_de.get(a.vacante_id, ""))
        return [a for a in orq.almacen.listar(Asignacion)
                if visible(a) and (estado is None or estado_de(a) == estado)]

    @app.post("/asignaciones/{joven_id}/{vacante_id}/decision")
    def decidir(joven_id: str, vacante_id: str, decision: Decision,
                _: Identidad = Depends(solo_orientador)) -> Asignacion:
        return orq.orientador_decidir(joven_id, vacante_id, decision.aprobar, decision.motivo)

    # ----- reacomodo -----
    @app.post("/asignaciones/{joven_id}/{vacante_id}/liberar")
    def liberar(joven_id: str, vacante_id: str, cuerpo: Liberacion,
                ident: Identidad = Depends(requerida)) -> ResultadoLiberacion:
        if cuerpo.tipo == "cancelacion_joven":
            exigir_joven(ident, joven_id)
        elif cuerpo.tipo == "retiro_empresa":
            exigir_dueno_vacante(ident, vacante_id)
        elif not ident.es_orientador:   # la inasistencia la registra el orientador
            raise sin_permiso("Solo el orientador registra inasistencias")
        liberada, nuevas = orq.liberar(joven_id, vacante_id, TipoCierre(cuerpo.tipo), cuerpo.motivo)
        return ResultadoLiberacion(liberada=liberada, nuevas=nuevas)

    @app.post("/asignaciones/{joven_id}/{vacante_id}/reprogramar")
    def reprogramar(joven_id: str, vacante_id: str, cuerpo: Motivo,
                    ident: Identidad = Depends(requerida)) -> Asignacion:
        exigir_joven(ident, joven_id)
        return orq.reprogramar_entrevista(joven_id, vacante_id, cuerpo.motivo)

    # ----- pesos del puntaje -----
    @app.get("/pesos")
    def ver_pesos() -> Pesos:
        return orq.pesos()

    @app.post("/pesos/simular")
    def simular_pesos(pesos: Pesos, _: Identidad = Depends(solo_orientador)) -> Simulacion:
        return orq.simular_pesos(pesos)

    @app.put("/pesos")
    def cambiar_pesos(cuerpo: CambioPesos, _: Identidad = Depends(solo_orientador)) -> Pesos:
        return orq.cambiar_pesos(cuerpo.pesos, cuerpo.motivo)

    # ----- transparencia -----
    @app.get("/trazas")
    def trazas(agente: str | None = None, limite: int = Query(default=200, ge=1, le=1000),
               _: Identidad = Depends(solo_orientador)) -> list[Traza]:
        return orq.almacen.trazas(agente, limite)

    @app.get("/mensajes")
    def mensajes(_: Identidad = Depends(solo_orientador)) -> list[dict]:
        return orq.almacen.mensajes()

    return app


app = crear_app(orquestador_desde_entorno(), cliente_llm=cliente_desde_entorno())
