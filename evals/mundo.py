"""Construye los modelos del contrato a partir de los casos JSON de `evals`.

Solo traduce datos: no decide nada ni altera el comportamiento real.
"""
from __future__ import annotations

from pathlib import Path

from agentes.matching import MatrizTraslados
from contrato.modelos import (
    DatosPersonales, HabilidadNivel, Joven, Pesos, RequisitoHabilidad, ResultadoMatching,
    Traslado, Turno, Vacante,
)

RAIZ = Path(__file__).resolve().parents[1]


def _turnos(valores) -> set[Turno]:
    return {Turno(v) for v in valores}


def joven(datos: dict) -> Joven:
    d = dict(datos)
    d["disponibilidad"] = _turnos(d["disponibilidad"])
    d["habilidades"] = [HabilidadNivel(**h) for h in d.get("habilidades", [])]
    return Joven(**d)


def vacante(datos: dict) -> Vacante:
    d = dict(datos)
    d["turnos"] = _turnos(d["turnos"])
    d.setdefault("estado", "publicada")
    d["habilidades_requeridas"] = [RequisitoHabilidad(**r)
                                   for r in d.get("habilidades_requeridas", [])]
    return Vacante(**d)


def matriz(traslados) -> MatrizTraslados | None:
    if traslados is None:
        return None
    return MatrizTraslados([Traslado(**t) for t in traslados])


def pesos(datos) -> Pesos | None:
    return Pesos(**datos) if datos else None


def datos_personales(mapa: dict | None) -> dict[str, DatosPersonales]:
    return {clave: DatosPersonales(**valor) for clave, valor in (mapa or {}).items()}


def resultado(datos: dict | None) -> ResultadoMatching | None:
    return ResultadoMatching(**datos) if datos else None


def cargar_casos(directorio: str | Path) -> list[dict]:
    """Lee todos los `*.json` del directorio (cada uno es una lista de casos)."""
    casos = []
    for archivo in sorted(Path(directorio).glob("*.json")):
        import json
        contenido = json.loads(archivo.read_text(encoding="utf-8"))
        if not isinstance(contenido, list):
            raise ValueError(f"{archivo} no contiene una lista de casos")
        casos.extend(contenido)
    return casos