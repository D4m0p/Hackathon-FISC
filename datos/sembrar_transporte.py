"""Siembra los datos de demostración y COMPLEMENTA sus traslados con `datos/transporte.csv`.

Conserva los traslados curados de la demo (tienen prioridad) y añade solo los pares nuevos
de la tabla estimada. No modifica `scripts/semilla_demo.py`: importa y reutiliza sus
funciones de carga (`cargar`, `credenciales_demo`), igual que `datos/cargar_muestra.py`.

Uso (desde la raíz del repositorio):
    .venv/bin/python datos/sembrar_transporte.py --base datos_app.db --reiniciar --matching
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
sys.path.insert(0, str(RAIZ / "datos"))

from contrato.modelos import Joven  # noqa: E402
from orquestador.arranque import orquestador_desde_entorno  # noqa: E402

import cargar_transporte  # noqa: E402  (datos/cargar_transporte.py: solo se reutiliza)
import semilla_demo  # noqa: E402  (scripts/semilla_demo.py: solo se reutiliza)

DEMO = RAIZ / "scripts" / "demo" / "datos_demo.json"


def sembrar(base: str, reiniciar: bool = False, con_matching: bool = False,
            franja: str = "valle") -> tuple:
    if reiniciar and base != ":memory:" and Path(base).exists():
        Path(base).unlink()
    orq = orquestador_desde_entorno(base)
    datos = json.loads(DEMO.read_text(encoding="utf-8"))
    resumen = semilla_demo.cargar(orq, datos, False)   # matching se corre al final, ya complementado
    resumen["traslados_demo"] = len(orq.almacen.traslados())
    total = cargar_transporte.cargar_en(orq.almacen, franja=franja, complementar=True)
    resumen["traslados_total"] = total
    resumen["traslados_agregados"] = total - resumen["traslados_demo"]
    if con_matching:
        r = orq.ejecutar_matching()
        resumen["asignaciones"] = [f"{a.joven_id}→{a.vacante_id}" for a in r.asignaciones]
        resumen["planes"] = sorted(j.id for j in orq.almacen.listar(Joven) if orq.plan_de(j.id))
    tokens = semilla_demo.credenciales_demo(orq, datos)
    return orq, datos, resumen, tokens


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default=os.getenv("RUTA_BASE_DATOS", "datos_app.db"))
    p.add_argument("--reiniciar", action="store_true", help="borra la base antes de cargar")
    p.add_argument("--matching", action="store_true", help="corre el matching al final")
    p.add_argument("--franja", default="valle", choices=sorted(cargar_transporte.FRANJAS))
    args = p.parse_args()

    _, datos, resumen, tokens = sembrar(args.base, args.reiniciar, args.matching, args.franja)
    print(f"Base: {args.base}")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")
    print("Tokens de demo (Authorization: Bearer <token>):")
    ids = sorted(r["joven"]["id"] for r in datos["jovenes"])
    print(f"  orientador: {tokens['orientador']} · jóvenes: {' '.join(ids)} "
          f"· empresas: demo-<empresa_id>")


if __name__ == "__main__":
    main()
