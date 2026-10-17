"""Límite de peticiones para anónimos en las rutas abiertas que cuestan (LLM o registros nuevos)."""
from __future__ import annotations

import math
import os
import threading
import time
from collections import deque

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from orquestador.almacen import Almacen

RUTAS_LIMITADAS = {("POST", "/perfil/cv"), ("POST", "/perfil/entrevista"), ("POST", "/perfil/transcribir"),
                   ("POST", "/perfil/declarar"),
                   ("POST", "/jovenes")}
VENTANA_S = 60.0
POR_DEFECTO = 30
MENSAJE = "Demasiadas solicitudes seguidas. Espere un momento e intente de nuevo."


def tope_desde_entorno() -> int:
    try:
        return max(1, int(os.getenv("LIMITE_ANONIMO_POR_MINUTO", POR_DEFECTO)))
    except ValueError:
        return POR_DEFECTO


class LimiteAnonimos:
    """Ventana deslizante de 60 s por IP, en memoria. Con token válido no se limita."""

    def __init__(self, app: ASGIApp, almacen: Almacen, tope: int):
        self.app, self.almacen, self.tope = app, almacen, tope
        self._golpes: dict[str, deque[float]] = {}
        self._cerrojo = threading.Lock()

    def _con_token_valido(self, scope: Scope) -> bool:
        for nombre, valor in scope["headers"]:
            if nombre == b"authorization":
                esquema, _, token = valor.decode("latin-1").partition(" ")
                return esquema.lower() == "bearer" and bool(token.strip()) \
                    and self.almacen.credencial(token.strip()) is not None
        return False

    def _espera(self, ip: str) -> int:
        """0 si la petición pasa (y queda anotada); si no, segundos hasta que se libere un cupo."""
        ahora = time.monotonic()
        with self._cerrojo:
            golpes = self._golpes.setdefault(ip, deque())
            while golpes and ahora - golpes[0] >= VENTANA_S:
                golpes.popleft()
            if len(golpes) >= self.tope:
                return max(1, math.ceil(VENTANA_S - (ahora - golpes[0])))
            golpes.append(ahora)
            if len(self._golpes) > 10_000:   # evita crecer sin fin con muchas IPs
                for k in [k for k, d in self._golpes.items() if not d or ahora - d[-1] >= VENTANA_S]:
                    del self._golpes[k]
            return 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or (scope["method"], scope["path"]) not in RUTAS_LIMITADAS \
                or self._con_token_valido(scope):
            await self.app(scope, receive, send)
            return
        ip = scope["client"][0] if scope.get("client") else "desconocida"
        espera = self._espera(ip)
        if espera:
            respuesta = JSONResponse(status_code=429, content={"detail": MENSAJE},
                                     headers={"Retry-After": str(espera)})
            await respuesta(scope, receive, send)
            return
        await self.app(scope, receive, send)
