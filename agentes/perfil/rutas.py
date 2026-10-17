"""Endpoints del agente Perfil. La API los monta con:

    from agentes.perfil.rutas import crear_router
    app.include_router(crear_router(orq))

Son abiertos (un joven nuevo aún no tiene token) y no guardan nada: devuelven las
habilidades propuestas; el frontend las muestra y luego llama a `POST /jovenes`.
En la traza solo quedan conteos, nunca el texto del CV.
"""
from __future__ import annotations

import base64
import binascii
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from contrato.modelos import Agente, Habilidad, Traza

from .agente import ErrorDocumento, MAX_CARACTERES_CV, Perfil, Respuesta, ResultadoPerfil
from .entrevista import MAX_PREGUNTAS, Pregunta
from .llm import ClienteLLM, cliente_desde_entorno
from .texto import alertas_inyeccion


class CuerpoCV(BaseModel):
    tipo: Literal["pdf", "imagen", "texto"]
    contenido_base64: str | None = Field(default=None, max_length=6_000_000)
    tipo_mime: str | None = None          # para imagen: image/jpeg, image/png, image/webp
    texto: str | None = Field(default=None, max_length=MAX_CARACTERES_CV)


class CuerpoEntrevista(BaseModel):
    respuestas: list[Respuesta] = Field(min_length=1, max_length=MAX_PREGUNTAS)


class CuerpoTranscribir(BaseModel):
    """Nota de voz (entrevista) o foto (volante de una oferta) → texto para revisar."""
    tipo: Literal["audio", "imagen"]
    contenido_base64: str = Field(min_length=1, max_length=7_000_000)
    tipo_mime: str = Field(min_length=1, max_length=80)
    documento: Literal["cv", "oferta"] = "cv"   # solo para imagen: qué se está leyendo


class Transcripcion(BaseModel):
    texto: str
    alertas: list[str] = []          # frases que parecen instrucciones al sistema


def crear_router(orq, cliente: ClienteLLM | None = None, usar_entorno: bool = True) -> APIRouter:
    router = APIRouter(prefix="/perfil", tags=["perfil"])
    cliente = cliente if cliente is not None else (cliente_desde_entorno() if usar_entorno else None)

    def agente() -> Perfil:
        return Perfil(orq.almacen.listar(Habilidad), cliente)

    def trazar(accion: str, entrada: dict, r: ResultadoPerfil) -> None:
        orq.almacen.registrar_traza(Traza(
            agente=Agente.perfil, accion=accion, entrada=entrada,
            salida={"habilidades": [h.codigo for h in r.habilidades],
                    "descartadas": len(r.descartadas), "alertas": len(r.alertas), "metodo": r.metodo},
            motivo=f"{len(r.habilidades)} habilidades con evidencia; "
                   f"{len(r.descartadas)} descartadas por la validación"
                   + (f"; {len(r.alertas)} posibles intentos de inyección" if r.alertas else "")))

    @router.get("/preguntas")
    def preguntas() -> list[Pregunta]:
        return agente().preguntas()

    @router.post("/cv")
    def desde_cv(cuerpo: CuerpoCV) -> ResultadoPerfil:
        perfil = agente()
        try:
            if cuerpo.tipo == "texto":
                if not cuerpo.texto or not cuerpo.texto.strip():
                    raise ErrorDocumento("Escriba o pegue el texto de su CV")
                texto = cuerpo.texto
            else:
                if not cuerpo.contenido_base64:
                    raise ErrorDocumento("Falta el archivo")
                try:
                    contenido = base64.b64decode(cuerpo.contenido_base64, validate=True)
                except (binascii.Error, ValueError):
                    raise ErrorDocumento("El archivo llegó dañado") from None
                texto = (perfil.texto_de_pdf(contenido) if cuerpo.tipo == "pdf"
                         else perfil.texto_de_imagen(contenido, cuerpo.tipo_mime or ""))
        except ErrorDocumento as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        r = perfil.desde_cv(texto)
        trazar("extraer_cv", {"tipo": cuerpo.tipo, "caracteres": len(texto)}, r)
        return r

    @router.post("/entrevista")
    def desde_entrevista(cuerpo: CuerpoEntrevista) -> ResultadoPerfil:
        r = agente().desde_entrevista(cuerpo.respuestas)
        trazar("entrevista", {"respuestas": len(cuerpo.respuestas)}, r)
        return r

    @router.post("/transcribir")
    def transcribir(cuerpo: CuerpoTranscribir) -> Transcripcion:
        """No decide nada: devuelve el texto para que la persona lo revise y lo corrija.
        Las habilidades salen después, por /perfil/entrevista o /perfil/cv (u /ofertas)."""
        perfil = agente()
        try:
            try:
                contenido = base64.b64decode(cuerpo.contenido_base64, validate=True)
            except (binascii.Error, ValueError):
                raise ErrorDocumento("El archivo llegó dañado") from None
            if cuerpo.tipo == "audio":
                texto = perfil.texto_de_audio(contenido, cuerpo.tipo_mime)
            else:
                que = "un volante o anuncio de empleo" if cuerpo.documento == "oferta" else "un currículum"
                texto = perfil.texto_de_imagen(contenido, cuerpo.tipo_mime, que)
        except ErrorDocumento as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        alertas = alertas_inyeccion(texto)
        orq.almacen.registrar_traza(Traza(
            agente=Agente.perfil, accion="transcribir",
            entrada={"tipo": cuerpo.tipo, "documento": cuerpo.documento, "bytes": len(contenido)},
            salida={"caracteres": len(texto), "alertas": len(alertas)},
            motivo=f"{'Nota de voz' if cuerpo.tipo == 'audio' else 'Foto'} transcrita "
                   f"({len(texto)} caracteres) para que la persona la revise"
                   + (f"; {len(alertas)} posibles intentos de inyección" if alertas else "")))
        return Transcripcion(texto=texto, alertas=alertas)

    return router
