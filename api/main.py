"""API HTTP del sistema. El frontend solo habla con esto.

Levantar:  .venv/bin/uvicorn api.main:app --reload --port 8010
Documentación interactiva: http://localhost:8010/docs
"""
from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from contrato.modelos import (
    Asignacion, CasiCalifica, Curso, DatosPersonales, Desglose, EstadoVacante, Joven, PlanFormacion,
    ResultadoAuditoria, ResultadoMatching, TipoCierre, Traslado, Traza, Vacante, Habilidad,
)
from orquestador import ErrorDeFlujo, NoEncontrado, Orquestador
from orquestador.arranque import orquestador_desde_entorno

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


class TarjetaVacante(BaseModel):
    vacante: Vacante
    desglose: Desglose


class TarjetaCandidato(BaseModel):
    """Lo que ve la empresa: sin nombre, género, edad ni contacto."""
    joven: Joven
    desglose: Desglose


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

def crear_app(orq: Orquestador) -> FastAPI:
    app = FastAPI(title="Empleo joven — sistema de agentes", version="0.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("ORIGENES_PERMITIDOS", "http://localhost:5173").split(","),
        allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(NoEncontrado)
    async def _no_encontrado(_: Request, e: NoEncontrado):
        return JSONResponse(status_code=404, content={"detail": str(e)})

    @app.exception_handler(ErrorDeFlujo)
    async def _error_de_flujo(_: Request, e: ErrorDeFlujo):
        return JSONResponse(status_code=400, content={"detail": str(e)})

    @app.get("/salud")
    def salud():
        return {"estado": "ok",
                "mercado": type(orq.mercado).__name__, "auditor": type(orq.auditor).__name__,
                "notificador": type(orq.notificador).__name__}

    # ----- datos de referencia (carga de la demo) -----
    @app.post("/traslados", status_code=204)
    def cargar_traslados(traslados: list[Traslado]):
        orq.almacen.guardar_traslados(traslados)

    @app.get("/traslados")
    def listar_traslados() -> list[Traslado]:
        return orq.almacen.traslados()

    @app.post("/habilidades", status_code=204)
    def cargar_habilidades(habilidades: list[Habilidad]):
        for h in habilidades:
            orq.almacen.guardar(h)

    @app.get("/habilidades")
    def listar_habilidades() -> list[Habilidad]:
        return orq.almacen.listar(Habilidad)

    @app.post("/cursos", status_code=204)
    def cargar_cursos(cursos: list[Curso]):
        for c in cursos:
            orq.almacen.guardar(c)

    @app.get("/cursos")
    def listar_cursos() -> list[Curso]:
        return orq.almacen.listar(Curso)

    # ----- empresas -----
    @app.post("/ofertas")
    def publicar_oferta(oferta: OfertaTexto) -> ResultadoPublicacion:
        try:
            v, r = orq.publicar_oferta(oferta.texto, oferta.empresa_id)
        except NotImplementedError as e:
            raise HTTPException(status_code=501, detail=str(e))
        return ResultadoPublicacion(vacante=v, auditoria=r)

    @app.post("/vacantes")
    def publicar_vacante(vacante: Vacante) -> ResultadoPublicacion:
        v, r = orq.publicar_vacante(vacante)
        return ResultadoPublicacion(vacante=v, auditoria=r)

    @app.get("/vacantes")
    def listar_vacantes(estado: EstadoVacante | None = None) -> list[Vacante]:
        vs = orq.almacen.listar(Vacante)
        return [v for v in vs if estado is None or v.estado == estado]

    @app.get("/vacantes/{vacante_id}")
    def obtener_vacante(vacante_id: str) -> Vacante:
        return orq._vacante(vacante_id)

    @app.post("/vacantes/{vacante_id}/publicar-bloqueada")
    def publicar_bloqueada(vacante_id: str, cuerpo: Motivo) -> Vacante:
        return orq.orientador_publicar_bloqueada(vacante_id, cuerpo.motivo)

    @app.get("/vacantes/{vacante_id}/tarjetas")
    def tarjetas_de_la_vacante(vacante_id: str) -> list[TarjetaCandidato]:
        return [TarjetaCandidato(joven=j, desglose=d) for j, d in orq.tarjetas_vacante(vacante_id)]

    # ----- jóvenes -----
    @app.post("/jovenes")
    def registrar_joven(registro: RegistroJoven) -> Joven:
        return orq.registrar_joven(registro.joven, registro.datos)

    @app.get("/jovenes")
    def listar_jovenes() -> list[Joven]:
        return orq.almacen.listar(Joven)

    @app.get("/jovenes/{joven_id}")
    def obtener_joven(joven_id: str) -> Joven:
        return orq._joven(joven_id)

    @app.get("/jovenes/{joven_id}/tarjetas")
    def tarjetas_del_joven(joven_id: str) -> list[TarjetaVacante]:
        return [TarjetaVacante(vacante=v, desglose=d) for v, d in orq.tarjetas_joven(joven_id)]

    @app.get("/jovenes/{joven_id}/plan")
    def plan_de_formacion(joven_id: str) -> PlanFormacion:
        orq._joven(joven_id)
        plan = orq.plan_de(joven_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Este joven no tiene plan de formación")
        return plan

    @app.get("/jovenes/{joven_id}/casi-califica")
    def casi(joven_id: str) -> list[CasiCalifica]:
        return orq.casi_califica(joven_id)

    @app.post("/deslizar")
    def deslizar(d: Deslizamiento) -> RespuestaDeslizamiento:
        return RespuestaDeslizamiento(
            interes_mutuo=orq.deslizar(d.actor, d.joven_id, d.vacante_id, d.le_interesa))

    # ----- matching y orientador -----
    @app.post("/matching")
    def ejecutar_matching() -> ResultadoMatching:
        return orq.ejecutar_matching()

    @app.get("/asignaciones")
    def listar_asignaciones(estado: Literal["pendiente", "aprobada", "rechazada", "cerrada"] | None = None
                            ) -> list[Asignacion]:
        def estado_de(a: Asignacion) -> str:
            if not a.vigente:
                return "cerrada"
            return {None: "pendiente", True: "aprobada", False: "rechazada"}[a.aprobada]
        return [a for a in orq.almacen.listar(Asignacion) if estado is None or estado_de(a) == estado]

    @app.post("/asignaciones/{joven_id}/{vacante_id}/decision")
    def decidir(joven_id: str, vacante_id: str, decision: Decision) -> Asignacion:
        return orq.orientador_decidir(joven_id, vacante_id, decision.aprobar, decision.motivo)

    # ----- reacomodo -----
    @app.post("/asignaciones/{joven_id}/{vacante_id}/liberar")
    def liberar(joven_id: str, vacante_id: str, cuerpo: Liberacion) -> ResultadoLiberacion:
        liberada, nuevas = orq.liberar(joven_id, vacante_id, TipoCierre(cuerpo.tipo), cuerpo.motivo)
        return ResultadoLiberacion(liberada=liberada, nuevas=nuevas)

    @app.post("/asignaciones/{joven_id}/{vacante_id}/reprogramar")
    def reprogramar(joven_id: str, vacante_id: str, cuerpo: Motivo) -> Asignacion:
        return orq.reprogramar_entrevista(joven_id, vacante_id, cuerpo.motivo)

    @app.post("/vacantes/{vacante_id}/cerrar")
    def cerrar_vacante(vacante_id: str, cuerpo: Motivo) -> ResultadoCierre:
        vacante, afectadas, nuevas = orq.cerrar_vacante(vacante_id, cuerpo.motivo)
        return ResultadoCierre(vacante=vacante, afectadas=afectadas, nuevas=nuevas)

    # ----- transparencia -----
    @app.get("/trazas")
    def trazas(agente: str | None = None, limite: int = Query(default=200, ge=1, le=1000)) -> list[Traza]:
        return orq.almacen.trazas(agente, limite)

    @app.get("/mensajes")
    def mensajes() -> list[dict]:
        return orq.almacen.mensajes()

    return app


app = crear_app(orquestador_desde_entorno())
