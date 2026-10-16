"""Construye el orquestador con lo que haya configurado en el entorno (.env)."""
from __future__ import annotations

import importlib
import os

from dotenv import load_dotenv

from .almacen import Almacen
from .flujo import Orquestador
from .notificador import desde_entorno


def agente_real(modulo: str, clase: str):
    """Usa el agente de C si ya existe (p. ej. `agentes.mercado.Mercado`); si no, None.
    Si el módulo existe pero falla al importarse, el error se muestra (no se oculta)."""
    try:
        mod = importlib.import_module(modulo)
    except ModuleNotFoundError as e:
        if e.name == modulo:
            return None
        raise
    cls = getattr(mod, clase, None)
    return cls() if cls is not None else None


def orquestador_desde_entorno(ruta_base: str | None = None) -> Orquestador:
    load_dotenv()
    almacen = Almacen(ruta_base or os.getenv("RUTA_BASE_DATOS", "datos_app.db"))
    return Orquestador(almacen,
                       mercado=agente_real("agentes.mercado", "Mercado"),
                       auditor=agente_real("agentes.auditor", "Auditor"),
                       notificador=desde_entorno())
