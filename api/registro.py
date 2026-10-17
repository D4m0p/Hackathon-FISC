"""Registro de peticiones y errores inesperados. Nunca se registran cuerpos, tokens ni query string."""
from __future__ import annotations

import logging
import re
import time
import traceback
import uuid

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("empleo.api")
CABECERA = "X-Id-Peticion"
_VALIDO = re.compile(r"[A-Za-z0-9]{1,32}")
MENSAJE_500 = "Ocurrió un error interno. Si se repite, avise al equipo con este código."


def _id_nuevo() -> str:
    return uuid.uuid4().hex[:8]


class RegistroPeticiones:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        traido = dict(scope["headers"]).get(CABECERA.lower().encode(), b"").decode("latin-1")
        id_peticion = traido if _VALIDO.fullmatch(traido) else _id_nuevo()
        scope.setdefault("state", {})["id_peticion"] = id_peticion
        inicio = time.perf_counter()
        estado = 500

        async def enviar(msg: Message) -> None:
            nonlocal estado
            if msg["type"] == "http.response.start":
                estado = msg["status"]
                msg.setdefault("headers", [])
                if not any(k.lower() == CABECERA.lower().encode() for k, _ in msg["headers"]):
                    msg["headers"] = [*msg["headers"], (CABECERA.lower().encode(), id_peticion.encode())]
            await send(msg)

        try:
            await self.app(scope, receive, enviar)
        finally:
            ms = (time.perf_counter() - inicio) * 1000
            log.info("%s %s %s %.1f ms id=%s", scope["method"], scope["path"], estado, ms, id_peticion)


async def error_inesperado(request: Request, e: Exception) -> JSONResponse:
    """500 genérico: el detalle va solo al log, con el mismo id que recibe el cliente."""
    id_error = getattr(request.state, "id_peticion", None) or _id_nuevo()
    log.error("Error inesperado id=%s en %s %s\n%s", id_error, request.method, request.url.path,
              "".join(traceback.format_exception(type(e), e, e.__traceback__)))
    return JSONResponse(status_code=500, content={"detail": MENSAJE_500, "id_error": id_error},
                        headers={CABECERA: id_error})
