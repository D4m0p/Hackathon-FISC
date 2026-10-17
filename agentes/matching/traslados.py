"""Tiempos y costos de traslado entre corregimientos (tabla precalculada).

Si un viaje no está en la tabla pero los dos corregimientos tienen su punto de OpenStreetMap
(`datos/corregimientos.csv`), se ESTIMA con la distancia en línea recta y el ritmo (minutos por
km) de los viajes que sí están en la tabla, tomando el percentil 75 (más lento que 3 de cada 4
viajes conocidos: conservador). La tarifa es la oficial del corredor de MiBus que usa
`datos/construir_transporte.py`. Queda marcado como estimado y se explica en los motivos.
Sin coordenadas con fuente no se estima nada: el matching sigue con `sin_datos`.
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache
from pathlib import Path

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

RUTA_COORDENADAS = Path(__file__).resolve().parents[2] / "datos" / "corregimientos.csv"
TARIFA_ESTIMADA = 0.75          # corredor de MiBus, tarifa oficial (datos/construir_transporte.py)
PERCENTIL_RITMO = 0.75          # conservador: más lento que 3 de cada 4 viajes de la tabla
MIN_VIAJES_PARA_ESTIMAR = 5     # con menos viajes de referencia no hay ritmo confiable


@lru_cache(maxsize=1)
def coordenadas_osm() -> dict[str, tuple[float, float]]:
    """{corregimiento: (lat, lon)} de OpenStreetMap, con fuente por fila. Vacío si no hay archivo."""
    try:
        with RUTA_COORDENADAS.open(encoding="utf-8") as f:
            return {r["codigo"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)}
    except (OSError, KeyError, ValueError):
        return {}


def distancia_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distancia en línea recta (haversine)."""
    (la1, lo1), (la2, lo2) = [(math.radians(x), math.radians(y)) for x, y in (a, b)]
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


class MatrizTraslados:
    """Busca un viaje en cualquiera de los dos sentidos."""

    def __init__(self, traslados: list[Traslado], coordenadas: dict[str, tuple[float, float]] | None = None):
        self._tabla: dict[tuple[str, str], Traslado] = {}
        for t in traslados:
            self._tabla[(t.origen, t.destino)] = t
        self._coordenadas = coordenadas or {}
        self._estimados: dict[frozenset, Traslado] = {}
        self.minutos_por_km = self._ritmo() if self._coordenadas else None

    def _ritmo(self) -> float | None:
        ritmos = sorted(
            t.minutos / d for t in self._tabla.values()
            if t.origen in self._coordenadas and t.destino in self._coordenadas
            and (d := distancia_km(self._coordenadas[t.origen], self._coordenadas[t.destino])) >= 1)
        if len(ritmos) < MIN_VIAJES_PARA_ESTIMAR:
            return None
        return ritmos[int(PERCENTIL_RITMO * (len(ritmos) - 1))]

    def es_estimado(self, origen: str, destino: str) -> bool:
        return frozenset((origen, destino)) in self._estimados

    def viaje(self, origen: str, destino: str) -> Traslado | None:
        t = self._tabla.get((origen, destino)) or self._tabla.get((destino, origen))
        if t is not None:
            return t
        if origen == destino and origen not in ZONAS_AMBIGUAS:
            return Traslado(origen=origen, destino=destino, **MISMO_CORREGIMIENTO)
        return self._estimar(origen, destino)

    def _estimar(self, origen: str, destino: str) -> Traslado | None:
        clave = frozenset((origen, destino))
        if clave in self._estimados:
            return self._estimados[clave]
        if (self.minutos_por_km is None or origen in ZONAS_AMBIGUAS or destino in ZONAS_AMBIGUAS
                or origen not in self._coordenadas or destino not in self._coordenadas):
            return None
        km = distancia_km(self._coordenadas[origen], self._coordenadas[destino])
        t = Traslado(origen=origen, destino=destino, minutos=max(1, round(km * self.minutos_por_km)),
                     costo=TARIFA_ESTIMADA)
        self._estimados[clave] = t
        return t


def costo_semanal(viaje: Traslado, dias_por_semana: int) -> float:
    """Ida y vuelta, todos los días de trabajo."""
    return round(viaje.costo * 2 * dias_por_semana, 2)


def costo_mensual(viaje: Traslado, dias_por_semana: int) -> float:
    return round(costo_semanal(viaje, dias_por_semana) * SEMANAS_POR_MES, 2)
