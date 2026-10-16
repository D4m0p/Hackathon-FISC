"""Carga los datos de demostración en la base de la app.

Uso (desde la raíz del repo):
    .venv/bin/python scripts/semilla_demo.py --reiniciar            # base limpia + datos
    .venv/bin/python scripts/semilla_demo.py --reiniciar --matching # además corre el matching

Pasa todo por el orquestador, así que las vacantes se auditan y queda traza de cada paso.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contrato.modelos import Curso, DatosPersonales, Habilidad, Joven, Traslado, Vacante  # noqa: E402
from orquestador import Orquestador  # noqa: E402
from orquestador.arranque import orquestador_desde_entorno  # noqa: E402

DATOS = RAIZ / "scripts" / "demo" / "datos_demo.json"


def cargar(orq: Orquestador, datos: dict, con_matching: bool = False) -> dict:
    orq.almacen.guardar_traslados([Traslado(**t) for t in datos["traslados"]])
    for h in datos["habilidades"]:
        orq.almacen.guardar(Habilidad(**h))
    for c in datos["cursos"]:
        orq.almacen.guardar(Curso(**c))
    bloqueadas = []
    for v in datos["vacantes"]:
        vacante, auditoria = orq.publicar_vacante(Vacante(**v))
        if not auditoria.aprobado:
            bloqueadas.append(vacante.id)
    for r in datos["jovenes"]:
        orq.registrar_joven(Joven(**r["joven"]), DatosPersonales(**r["datos"]))
    mutuos = 0
    for d in datos["deslizamientos"]:
        if orq.deslizar(d["actor"], d["joven_id"], d["vacante_id"], d["le_interesa"]):
            mutuos += 1
    resumen = {"vacantes": len(datos["vacantes"]), "bloqueadas": bloqueadas,
               "jovenes": len(datos["jovenes"]), "cursos": len(datos["cursos"]),
               "interes_mutuo": mutuos}
    if con_matching:
        r = orq.ejecutar_matching()
        resumen["asignaciones"] = [f"{a.joven_id}→{a.vacante_id}" for a in r.asignaciones]
        resumen["planes"] = sorted(j.id for j in orq.almacen.listar(Joven) if orq.plan_de(j.id))
    return resumen


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default=os.getenv("RUTA_BASE_DATOS", "datos_app.db"))
    p.add_argument("--reiniciar", action="store_true", help="borra la base antes de cargar")
    p.add_argument("--matching", action="store_true", help="corre el matching al final")
    args = p.parse_args()

    if args.reiniciar and args.base != ":memory:" and Path(args.base).exists():
        Path(args.base).unlink()
    orq = orquestador_desde_entorno(args.base)
    resumen = cargar(orq, json.loads(DATOS.read_text(encoding="utf-8")), args.matching)
    print(f"Base: {args.base}")
    print(f"Auditor: {type(orq.auditor).__name__}")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")


if __name__ == "__main__":
    main()
