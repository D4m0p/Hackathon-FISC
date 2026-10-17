"""Carga la tabla de transporte `datos/transporte.csv` como modelos `Traslado`.

El CSV es dirigido y trae dos filas por par (hora pico y hora valle). Para el contrato
`Traslado` (un solo tiempo por par) se elige una franja, por defecto `valle`. Los tiempos
son ESTIMACIONES del equipo (ver `datos/FUENTES_TRANSPORTE.md`), no datos oficiales.

No modifica nada de `scripts/`: solo expone funciones reutilizables y una interfaz de
línea de comandos para inspeccionar la tabla.

Uso (desde la raíz del repositorio):
    .venv/bin/python datos/cargar_transporte.py --resumen
    .venv/bin/python datos/cargar_transporte.py --cobertura    # ids del stack de demo
    .venv/bin/python datos/cargar_transporte.py --json
    .venv/bin/python datos/cargar_transporte.py --para-demo    # con los alias de demo
    .venv/bin/python datos/cargar_transporte.py --franja pico --json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from contrato.modelos import Traslado  # noqa: E402

RUTA_POR_DEFECTO = Path(__file__).resolve().parent / "transporte.csv"

COLUMNAS_OBLIGATORIAS = {
    "origen", "destino", "modo", "ruta", "tiempo_min", "tarifa_usd", "transbordos",
    "franja_horaria", "fuente_url", "fecha_consulta", "confianza", "tipo_dato",
}
FRANJAS = {"pico", "valle"}

# Identificadores que usa el stack de demo y no coinciden 1 a 1 con los corregimientos
# verificados de la tabla.
#
# `ALIAS_DEMO`: se traducen porque tienen una equivalencia clara y acotada. `la_chorrera` es
# la ciudad de La Chorrera, formada por los barrios Colón y Balboa (dos corregimientos del
# mismo núcleo urbano); se toma Barrio Colón como su centro. Aproximación pequeña y
# documentada (ver `datos/FUENTES_TRANSPORTE.md`).
ALIAS_DEMO = {"la_chorrera": "barrio_colon"}

# `AMBIGUOS_DEMO`: ids que designan una zona administrativa (p. ej. un DISTRITO) y no una
# ubicación puntual, así que NO se traducen a un corregimiento: hacerlo presentaría una
# ubicación genérica como si fuera exacta y produciría tiempos de viaje engañosos.
#   - san_miguelito: es el distrito de San Miguelito (9 corregimientos, ~50 km²). Su hub de
#     transporte (estación de intercambio San Miguelito L1/L2) está en Victoriano Lorenzo,
#     pero un joven en "san_miguelito" puede estar en cualquiera de los 9 corregimientos y
#     algunos (Omar Torrijos, Arnulfo Arias) no tienen nodo verificado. Se deja sin traducir:
#     el matching, sin cambios, lo trata como `sin_datos` (el cargador no inventa datos).
AMBIGUOS_DEMO = {"san_miguelito": "San Miguelito"}

# Ids de corregimiento usados por los datos de demostración (para el chequeo de cobertura).
IDS_DEMO = ("arraijan", "bella_vista", "betania", "juan_diaz", "la_chorrera",
            "san_francisco", "san_miguelito", "tocumen")


def leer(ruta: str | Path | None = None) -> list[dict[str, str]]:
    camino = Path(ruta) if ruta is not None else RUTA_POR_DEFECTO
    with camino.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        faltan = COLUMNAS_OBLIGATORIAS - set(lector.fieldnames or [])
        if faltan:
            raise ValueError(f"{camino} no tiene las columnas obligatorias: {sorted(faltan)}")
        return list(lector)


def a_traslados(filas: list[dict[str, str]], franja: str = "valle") -> list[Traslado]:
    if franja not in FRANJAS:
        raise ValueError(f"franja inválida: {franja!r}; use una de {sorted(FRANJAS)}")
    por_par: dict[tuple[str, str], dict[str, str]] = {}
    for fila in filas:
        if fila["franja_horaria"] != franja:
            continue
        if fila["tipo_dato"] == "desconocido" or not fila["tiempo_min"].strip():
            continue   # sin datos: el matching lo tratará como `sin_datos`
        por_par[(fila["origen"], fila["destino"])] = fila
    return [
        Traslado(origen=o, destino=d, minutos=int(f["tiempo_min"]), costo=float(f["tarifa_usd"]))
        for (o, d), f in sorted(por_par.items())
    ]


def cargar_traslados(ruta: str | Path | None = None, franja: str = "valle") -> list[Traslado]:
    return a_traslados(leer(ruta), franja)


def mezclar(existentes: list[Traslado], nuevos: list[Traslado]) -> list[Traslado]:
    """Une dos listas de `Traslado` por clave `(origen, destino)`.

    Conserva el traslado de `existentes` cuando el par se repite (tiene prioridad) y añade
    solo los pares de `nuevos` que faltan. Determinista (orden por clave) y sin duplicados.
    """
    por_par: dict[tuple[str, str], Traslado] = {(t.origen, t.destino): t for t in nuevos}
    for t in existentes:
        por_par[(t.origen, t.destino)] = t
    return [por_par[clave] for clave in sorted(por_par)]


def cargar_en(almacen, ruta: str | Path | None = None, franja: str = "valle",
              complementar: bool = True) -> int:
    """Guarda los traslados en el almacén (misma vía que `scripts/semilla_demo.py`).

    Con `complementar=True` (por defecto) combina los traslados que ya tenga el almacén con
    los de `cargar_para_demo()`, conservando los pares existentes (p. ej. los curados de la
    demo) y añadiendo solo los nuevos. Con `complementar=False` reemplaza toda la tabla por
    los de `cargar_traslados()`. Determinista e idempotente; devuelve el total guardado.
    """
    nuevos = cargar_para_demo(ruta, franja) if complementar else cargar_traslados(ruta, franja)
    traslados = mezclar(almacen.traslados(), nuevos) if complementar else nuevos
    almacen.guardar_traslados(traslados)
    return len(traslados)


def zonas(ruta: str | Path | None = None) -> set[str]:
    filas = leer(ruta)
    return {f["origen"] for f in filas} | {f["destino"] for f in filas}


def cobertura(ids=IDS_DEMO, ruta: str | Path | None = None) -> dict:
    """Cómo se relaciona un conjunto de ids con los corregimientos de la tabla.

    Devuelve:
      - `cubiertos`: id que existe tal cual como corregimiento en la tabla;
      - `alias`: id -> corregimiento con equivalencia clara y acotada (`ALIAS_DEMO`);
      - `ambiguos`: id -> zona administrativa que NO se traduce porque no es una ubicación
        puntual (p. ej. un distrito con varios corregimientos posibles);
      - `faltantes`: ids sin equivalente (el matching los trata como `sin_datos`).
    """
    disponibles = zonas(ruta)
    cubiertos, alias, ambiguos, faltantes = set(), {}, {}, []
    for i in ids:
        if i in disponibles:
            cubiertos.add(i)
        elif ALIAS_DEMO.get(i) in disponibles:
            alias[i] = ALIAS_DEMO[i]
        elif i in AMBIGUOS_DEMO:
            ambiguos[i] = AMBIGUOS_DEMO[i]
        else:
            faltantes.append(i)
    return {"cubiertos": sorted(cubiertos), "alias": alias,
            "ambiguos": ambiguos, "faltantes": sorted(faltantes)}


def cargar_para_demo(ruta: str | Path | None = None, franja: str = "valle") -> list[Traslado]:
    """Traslados de la tabla con los `ALIAS_DEMO` aplicados (ida y vuelta).

    Mantiene los ids de la tabla y añade, para cada par, las variantes con el id de demo,
    de modo que un joven/vacante con id antiguo (p. ej. `la_chorrera`) encuentre su par.
    """
    base = cargar_traslados(ruta, franja)
    inverso: dict[str, list[str]] = {}
    for demo_id, tabla_id in ALIAS_DEMO.items():
        inverso.setdefault(tabla_id, []).append(demo_id)
    salida: dict[tuple[str, str], Traslado] = {(t.origen, t.destino): t for t in base}
    for t in base:
        for o in [t.origen, *inverso.get(t.origen, [])]:
            for d in [t.destino, *inverso.get(t.destino, [])]:
                if o != d:
                    salida.setdefault((o, d), Traslado(
                        origen=o, destino=d, minutos=t.minutos, costo=t.costo))
    return [salida[k] for k in sorted(salida)]


def resumen(filas: list[dict[str, str]]) -> dict:
    zonas = {f["origen"] for f in filas} | {f["destino"] for f in filas}
    pares = {(f["origen"], f["destino"]) for f in filas}
    tipos = sorted({f["tipo_dato"] for f in filas})
    distritos = sorted(
        {f.get("distrito_origen", "") for f in filas} |
        {f.get("distrito_destino", "") for f in filas} - {""})
    conocidas = {(f["origen"], f["destino"]) for f in filas if f["tipo_dato"] != "desconocido"}
    return {
        "filas": len(filas),
        "zonas": len(zonas),
        "distritos": distritos,
        "pares_dirigidos": len(pares),
        "pares_con_datos": len(conocidas),
        "pares_desconocidos": len(pares) - len(conocidas),
        "franjas": sorted({f["franja_horaria"] for f in filas}),
        "tipos_dato": tipos,
        "fuentes": sorted({f["fuente_url"] for f in filas if f["fuente_url"]}),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ruta", default=str(RUTA_POR_DEFECTO))
    p.add_argument("--franja", default="valle", choices=sorted(FRANJAS))
    p.add_argument("--resumen", action="store_true", help="estadísticas de la tabla")
    p.add_argument("--cobertura", action="store_true",
                   help="cobertura de los ids del stack de demo")
    p.add_argument("--para-demo", action="store_true",
                   help="imprime los Traslado con los alias de demo aplicados")
    p.add_argument("--json", action="store_true", help="imprime los Traslado en JSON")
    args = p.parse_args()

    filas = leer(args.ruta)
    if args.cobertura or not (args.json or args.para_demo):
        print(json.dumps({**resumen(filas), "cobertura_demo": cobertura(IDS_DEMO, args.ruta)},
                         ensure_ascii=False, indent=2))
    if args.para_demo:
        traslados = cargar_para_demo(args.ruta, args.franja)
        print(json.dumps([t.model_dump() for t in traslados], ensure_ascii=False, indent=2))
    elif args.json:
        traslados = cargar_traslados(args.ruta, args.franja)
        print(json.dumps([t.model_dump() for t in traslados], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
