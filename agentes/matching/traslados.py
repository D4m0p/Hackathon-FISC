"""Tiempos y costos de traslado entre corregimientos (tabla precalculada)."""
from __future__ import annotations

from contrato.modelos import Traslado

# Si la tabla no trae el viaje dentro del mismo corregimiento, se asume esto.
MISMO_CORREGIMIENTO = dict(minutos=15, costo=0.0)

# Ids que NO son corregimientos (zonas administrativas que agrupan varios, p. ej. un
# distrito). A estos no se les aplica el supuesto de "mismo corregimiento": si el joven y
# la vacante coinciden en un id así, no se confirma una coincidencia geográfica y `viaje()`
# devuelve `None`, de modo que el matching usa su mecanismo existente `sin_datos` (no se
# inventa un viaje local de 15 min ni una ruta). Hoy solo `san_miguelito`, que es el
# distrito de San Miguelito (9 corregimientos), no un corregimiento concreto; ver
# `datos/FUENTES_TRANSPORTE.md` y `datos/cargar_transporte.py::AMBIGUOS_DEMO` (hay una
# prueba de consistencia que mantiene ambas listas sincronizadas).
ZONAS_AMBIGUAS = frozenset({"san_miguelito"})

SEMANAS_POR_MES = 4.33


class MatrizTraslados:
    """Busca un viaje en cualquiera de los dos sentidos."""

    def __init__(self, traslados: list[Traslado]):
        self._tabla: dict[tuple[str, str], Traslado] = {}
        for t in traslados:
            self._tabla[(t.origen, t.destino)] = t

    def viaje(self, origen: str, destino: str) -> Traslado | None:
        t = self._tabla.get((origen, destino)) or self._tabla.get((destino, origen))
        if t is not None:
            return t
        if origen == destino and origen not in ZONAS_AMBIGUAS:
            return Traslado(origen=origen, destino=destino, **MISMO_CORREGIMIENTO)
        return None


def costo_semanal(viaje: Traslado, dias_por_semana: int) -> float:
    """Ida y vuelta, todos los días de trabajo."""
    return round(viaje.costo * 2 * dias_por_semana, 2)


def costo_mensual(viaje: Traslado, dias_por_semana: int) -> float:
    return round(costo_semanal(viaje, dias_por_semana) * SEMANAS_POR_MES, 2)
