"""Tendencias del mercado por zona.

Solo sobre datos que el sistema ya tiene (`Vacante` almacenadas): cuenta qué
habilidades pide cada corregimiento. No consulta fuentes externas ni inventa
demanda. Con pocas vacantes el resultado es ilustrativo, no evidencia.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from contrato.modelos import Habilidad, Vacante


def tendencias_por_zona(vacantes: list[Vacante], taxonomia: dict[str, Habilidad],
                        top: int = 5) -> dict[str, list[tuple[str, int]]]:
    """Habilidades más pedidas por corregimiento, de mayor a menor.

    Cada conteo es cuántas vacantes de esa zona requieren la habilidad. Solo se
    cuentan códigos de la taxonomía; los desconocidos se ignoran.
    """
    conteo: dict[str, Counter] = defaultdict(Counter)
    for v in vacantes:
        for r in v.habilidades_requeridas:
            if r.codigo in taxonomia:
                conteo[v.corregimiento][r.codigo] += 1
    return {zona: sorted(c.items(), key=lambda par: (-par[1], par[0]))[:top]
            for zona, c in sorted(conteo.items())}


def vacantes_por_zona(vacantes: list[Vacante]) -> dict[str, int]:
    """Cuántas vacantes hay por corregimiento."""
    return dict(sorted(Counter(v.corregimiento for v in vacantes).items()))