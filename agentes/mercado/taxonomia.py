"""Acceso a la taxonomía de habilidades existente.

No define códigos nuevos: lee la misma lista que usa el resto del sistema. La
fuente por defecto es el archivo de datos de referencia; si existe
`datos/habilidades.json` se prefiere ese, y siempre se puede indicar otra ruta.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from contrato.modelos import Habilidad

RAIZ = Path(__file__).resolve().parents[2]
RUTA_DATOS = RAIZ / "datos" / "habilidades.json"
RUTA_DEMO = RAIZ / "scripts" / "demo" / "datos_demo.json"


def ruta_por_defecto() -> Path:
    desde_entorno = os.getenv("MERCADO_REFERENCIA")
    if desde_entorno:
        return Path(desde_entorno)
    if RUTA_DATOS.exists():
        return RUTA_DATOS
    return RUTA_DEMO


def _leer(ruta: str | Path | None) -> dict:
    camino = Path(ruta) if ruta is not None else ruta_por_defecto()
    datos = json.loads(camino.read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        raise ValueError(f"El archivo de referencia {camino} no tiene el formato esperado")
    return datos


def cargar_referencia(ruta: str | Path | None = None) -> tuple[dict[str, Habilidad], set[str]]:
    """Devuelve (taxonomía por código, corregimientos conocidos)."""
    datos = _leer(ruta)
    taxonomia = {}
    for h in datos.get("habilidades", []):
        habilidad = Habilidad(**h)
        taxonomia[habilidad.codigo] = habilidad
    corregimientos: set[str] = set()
    for t in datos.get("traslados", []):
        corregimientos.add(t["origen"])
        corregimientos.add(t["destino"])
    return taxonomia, corregimientos