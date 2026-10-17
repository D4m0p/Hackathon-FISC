"""Carga la MUESTRA SINTÉTICA (`datos/demo_muestra/datos_muestra.json`) en una base.

Los registros son ficticios (ver el `_nota` del JSON y `datos/demo_muestra/LEEME.md`):
sirven para demostrar el flujo completo, NO como vacantes reales.

No modifica `scripts/semilla_demo.py`: importa y reutiliza sus funciones de carga
(`cargar`, `credenciales_demo`), para no duplicar lógica ni pisar el trabajo de su dueño.

Uso (desde la raíz del repositorio):
    .venv/bin/python datos/cargar_muestra.py --base datos_muestra.db --reiniciar --matching
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from orquestador.arranque import orquestador_desde_entorno  # noqa: E402

import semilla_demo  # noqa: E402  (scripts/semilla_demo.py: solo se reutiliza)

MUESTRA = Path(__file__).resolve().parent / "demo_muestra" / "datos_muestra.json"


def cargar_muestra(base: str, reiniciar: bool = False, con_matching: bool = False) -> tuple:
    if reiniciar and base != ":memory:" and Path(base).exists():
        Path(base).unlink()
    orq = orquestador_desde_entorno(base)
    datos = json.loads(MUESTRA.read_text(encoding="utf-8"))
    resumen = semilla_demo.cargar(orq, datos, con_matching)
    tokens = semilla_demo.credenciales_demo(orq, datos)
    return orq, datos, resumen, tokens


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default=os.getenv("RUTA_BASE_DATOS", "datos_muestra.db"))
    p.add_argument("--reiniciar", action="store_true", help="borra la base antes de cargar")
    p.add_argument("--matching", action="store_true", help="corre el matching al final")
    args = p.parse_args()

    _, datos, resumen, tokens = cargar_muestra(args.base, args.reiniciar, args.matching)
    print(f"Base: {args.base}")
    print("Muestra SINTÉTICA (ficticia): no representa ofertas reales.")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")
    print("Tokens de la muestra (Authorization: Bearer <token>):")
    ids = sorted(r["joven"]["id"] for r in datos["jovenes"])
    print(f"  orientador: {tokens['orientador']} · jóvenes: {', '.join(ids)} "
          f"· empresas: demo-<empresa_id>")


if __name__ == "__main__":
    main()
