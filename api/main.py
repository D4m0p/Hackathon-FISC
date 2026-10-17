"""API HTTP del sistema. El frontend solo habla con esto.

Levantar:  .venv/bin/uvicorn api.main:app --reload --port 8010 --timeout-keep-alive 30
Documentación interactiva: http://localhost:8010/docs
"""
from __future__ import annotations

import difflib
import json
import os
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from contrato.modelos import (
    Asignacion, CasiCalifica, Curso, DatosPersonales, Desglose, EstadoVacante, Joven, PlanFormacion,
    Pesos, ResultadoAuditoria, ResultadoMatching, TipoCierre, Traslado, Traza, Vacante, Habilidad,
)
from orquestador import (
    DemandaCurso, DemostracionContrafactual, Reserva, ErrorDeFlujo, HistoriaJoven, NoEncontrado, Orquestador, Simulacion, Tendencias,
)
from agentes.perfil import ClienteLLM, cliente_desde_entorno
from agentes.perfil.rutas import crear_router as rutas_perfil
from orquestador.arranque import orquestador_desde_entorno
from agentes.matching.traslados import coordenadas_osm
from orquestador.interfaces import es_oferta_incompleta, faltantes_de

from .limites import LimiteAnonimos, tope_desde_entorno
from .registro import RegistroPeticiones, error_inesperado
from .seguridad import Identidad, Rol, dependencias, nuevo_token, sin_permiso
from .rutas_impacto import crear_router as rutas_impacto

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


class PedidoReserva(BaseModel):
    joven_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$", max_length=64)
    motivo: str = Field(default="", max_length=500)


class ResultadoReserva(BaseModel):
    curso: Curso
    reserva: Reserva


MAX_BYTES_FOTO = 2 * 1024 * 1024
_FIRMAS_FOTO = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "image/webp": (b"RIFF",)}


class FotoSubida(BaseModel):
    tipo_mime: Literal["image/jpeg", "image/png", "image/webp"]
    contenido_base64: str = Field(min_length=8, max_length=2_800_000)


def _imagen_valida(tipo: str, datos: bytes) -> bool:
    """La foto debe ser de verdad del tipo que dice (no se confía en la extensión ni en el MIME)."""
    if not datos.startswith(_FIRMAS_FOTO[tipo]):
        return False
    return tipo != "image/webp" or datos[8:12] == b"WEBP"


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

    # Cifra de impacto: cuántos pares joven–vacante descarta el sistema y por qué.
    app.include_router(rutas_impacto(orq, solo_orientador, requerida))

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
    def validar_ubicacion(codigo: str) -> None:
        """Una ubicación que no conocemos no se acepta en silencio (no saldría en el mapa ni
        tendría viajes, y nadie haría match): 400 con los corregimientos de nombre más parecido."""
        conocidos = {t.origen for t in orq.almacen.traslados()} | {t.destino for t in orq.almacen.traslados()}
        if not conocidos or codigo in conocidos or codigo in coordenadas_osm():
            return
        todos = sorted(conocidos | set(coordenadas_osm()))
        parecidos = difflib.get_close_matches(codigo, todos, n=3, cutoff=0.3) or todos[:3]
        nombres = ", ".join(p.replace("_", " ").title() for p in parecidos)
        raise HTTPException(status_code=400, detail=(
            f"No tenemos la ubicación «{codigo.replace('_', ' ')}» en el mapa ni datos de cómo llegar. "
            f"Elija el corregimiento más cercano de la lista (por ejemplo: {nombres})."))

    @app.post("/demo/reiniciar")
    def reiniciar_demo(_: Identidad = Depends(solo_orientador)) -> dict:
        """Vuelve a los datos de demostración: borra todo y carga la semilla (con matching)."""
        if os.getenv("PERMITIR_REINICIAR_DEMO", "1") == "0":
            raise HTTPException(status_code=403, detail="El reinicio de la demostración está desactivado")
        from scripts.semilla_demo import DATOS, cargar, credenciales_demo
        datos = json.loads(Path(DATOS).read_text(encoding="utf-8"))
        automatico, orq.automatico = orq.automatico, False   # carga masiva: sin disparos automáticos
        try:
            orq.almacen.vaciar()
            resumen = cargar(orq, datos, con_matching=True)
            credenciales_demo(orq, datos)
        finally:
            orq.automatico = automatico
        return {"vacantes": resumen["vacantes"], "jovenes": resumen["jovenes"], "cursos": resumen["cursos"]}

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
            validar_ubicacion(c.corregimiento)
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
        validar_ubicacion(vacante.corregimiento)
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
        validar_ubicacion(registro.joven.corregimiento)
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

    # ----- foto del joven: la ven él, el orientador y SOLO la empresa con interés mutuo -----
    @app.put("/jovenes/{joven_id}/foto", status_code=204)
    def subir_foto(joven_id: str, foto: FotoSubida, ident: Identidad = Depends(requerida)):
        exigir_joven(ident, joven_id)
        orq._joven(joven_id)
        import base64
        import binascii
        try:
            datos = base64.b64decode(foto.contenido_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="La foto llegó dañada")
        if len(datos) > MAX_BYTES_FOTO:
            raise HTTPException(status_code=413, detail="La foto pesa más de 2 MB")
        if not _imagen_valida(foto.tipo_mime, datos):
            raise HTTPException(status_code=400, detail="El archivo no es una imagen JPG, PNG o WebP válida")
        orq.almacen.guardar_foto(joven_id, foto.tipo_mime, datos)

    @app.delete("/jovenes/{joven_id}/foto", status_code=204)
    def borrar_foto(joven_id: str, ident: Identidad = Depends(requerida)):
        exigir_joven(ident, joven_id)
        orq.almacen.borrar_foto(joven_id)

    def _empresa_puede_ver_foto(empresa_id: str, joven_id: str) -> bool:
        def es_suya(vacante_id: str) -> bool:
            v = orq.almacen.obtener(Vacante, vacante_id)
            return v is not None and v.empresa_id == empresa_id
        asignaciones = {a.vacante_id: a for a in orq.almacen.asignaciones(joven_id=joven_id)}
        if any(a.vigente and a.aprobada and es_suya(v) for v, a in asignaciones.items()):
            return True
        si = {(d["actor"], d["vacante_id"]) for d in orq.almacen.deslizamientos_de(joven_id) if d["le_interesa"]}
        for actor, v in si:
            a = asignaciones.get(v)
            descartada = a is not None and (not a.vigente or a.aprobada is False)
            if actor == "empresa" and ("joven", v) in si and es_suya(v) and not descartada:
                return True
        return False

    @app.get("/jovenes/{joven_id}/foto")
    def ver_foto(joven_id: str, ident: Identidad = Depends(requerida)):
        """La empresa solo la ve cuando ya aceptó a la persona y a ella también le interesa la
        vacante (interés mutuo), o con una entrevista aprobada: elige por habilidades, sin foto, y
        la foto aparece después de decidir. Si el orientador rechaza el match o se cancela, deja
        de verla. A los demás, 404 (no se revela nada)."""
        permitido = ident.es_joven(joven_id) or (
            ident.rol == "empresa" and _empresa_puede_ver_foto(ident.sujeto, joven_id))
        foto = orq.almacen.foto(joven_id) if permitido else None
        if foto is None:
            raise HTTPException(status_code=404, detail="Sin foto")
        return Response(content=foto[1], media_type=foto[0],
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

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

    # ----- centros de formación (tercer lado del mercado) -----
    @app.get("/centros/{centro}/demanda")
    def demanda_del_centro(centro: str, ident: Identidad = Depends(requerida)) -> list[DemandaCurso]:
        """Quiénes necesitan cada curso del centro, en orden determinístico (sin datos personales)."""
        if not ident.es_centro(centro):
            raise sin_permiso()
        return orq.demanda_centro(centro)

    @app.post("/cursos/{curso_id}/reservas")
    def reservar_cupo(curso_id: str, pedido: PedidoReserva, ident: Identidad = Depends(requerida)) -> ResultadoReserva:
        """El centro dueño del curso (o el orientador) reserva un cupo para un joven."""
        curso = orq.almacen.obtener(Curso, curso_id)
        if curso is None:
            raise NoEncontrado(f"No existe el curso {curso_id}")
        if not ident.es_centro(curso.centro):
            raise sin_permiso("Solo el centro dueño del curso puede reservar cupos")
        curso, reserva = orq.reservar_cupo(curso_id, pedido.joven_id, pedido.motivo)
        return ResultadoReserva(curso=curso, reserva=reserva)

    # ----- transparencia de los agentes -----
    @app.get("/mercado/tendencias")
    def tendencias(top: int = Query(default=5, ge=1, le=20)) -> Tendencias:
        """Habilidades más pedidas por zona (agente de Mercado). Público: orienta a los jóvenes."""
        return orq.tendencias(top)

    @app.get("/auditoria/contrafactual/{joven_id}")
    def contrafactual(joven_id: str, _: Identidad = Depends(solo_orientador)) -> DemostracionContrafactual:
        """El mismo joven en cada corregimiento: solo cambian traslado y salario (Auditor)."""
        return orq.demostrar_contrafactual(joven_id)

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
