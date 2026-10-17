"""Construye la tabla de transporte `datos/transporte.csv` a partir de un modelo.

Aviso importante: **los tiempos de esta tabla son estimaciones del equipo**, no datos
oficiales por par origen-destino (MiBus y el Metro no publican tiempos entre
corregimientos). Las tarifas, en cambio, se derivan de las tarifas oficiales de MiBus
y del Metro. El método completo, las fuentes y la cobertura se documentan en
`datos/FUENTES_TRANSPORTE.md`.

El modelo es un grafo de nodos reales (estaciones del Metro y zonas pagas/paradas de
MiBus) sobre el que se calcula la ruta más corta; a cada corregimiento se le asigna un
nodo de acceso. Los corregimientos para los que **no** hay evidencia de un nodo troncal
que los sirva quedan como `desconocido`: sus pares se emiten con `tipo_dato=desconocido`
y `tiempo_min` vacío, para que el cargador los omita y el matching use su mecanismo
`sin_datos` (no se inventan paradas, conexiones ni tiempos). Todo es determinístico:
la misma corrida produce el mismo archivo.

Uso (desde la raíz del repositorio):
    .venv/bin/python datos/construir_transporte.py                 # escribe datos/transporte.csv
    .venv/bin/python datos/construir_transporte.py --salida OTRO.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA_POR_DEFECTO = Path(__file__).resolve().parent / "transporte.csv"

FECHA_CONSULTA = "2026-10-16"

# Rapidez del Metro de Panamá: Albrook-San Isidro (13 segmentos) en 28:30 min.
# https://elmetrodepanama.com/parametros/  -> ~2.19 min por segmento.
SEG_METRO = 28.5 / 13

# Penalizaciones estimadas de transbordo (minutos de espera+caminata).
TRANSBORDO_BUS_METRO = 8.0   # entre una parada/zona paga y una estación
TRANSBORDO_METRO = 7.0       # entre Línea 1 y Línea 2 en San Miguelito

# Factor de hora pico aplicado a los tiempos base (valle). Es un supuesto del equipo.
FACTOR_PICO = 1.3

FUENTE_METRO = "https://elmetrodepanama.com/tarifa-del-metro/"
FUENTE_METRO_TIEMPO = "https://elmetrodepanama.com/parametros/"
FUENTE_MIBUS = "https://www.mibus.com.pa/guia-del-usuario/"

# Estaciones del Metro (mapa oficial de líneas 1 y 2).
NODOS_L1 = [
    "albrook", "5_de_mayo", "loteria", "santo_tomas", "iglesia_del_carmen",
    "via_argentina", "fernandez_de_cordoba", "el_ingenio", "12_de_octubre",
    "pueblo_nuevo", "san_miguelito", "pan_de_azucar", "los_andes", "san_isidro",
]
NODOS_L2 = [
    "san_miguelito", "paraiso", "cincuentenario", "villa_lucre", "cerro_viento",
    "pedregal", "don_bosco", "corredor_sur", "las_mananitas", "hospital_del_este",
    "altos_de_tocumen", "24_de_diciembre", "nuevo_tocumen",
]

# Aristas de bus (corredores). Los minutos son estimaciones del equipo.
ARISTAS_BUS = [
    ("albrook", "arraijan", 35, "corredor_oeste"),
    ("5_de_mayo", "arraijan", 40, "corredor_oeste"),
    ("arraijan", "la_chorrera", 30, "corredor_oeste"),
    ("albrook", "la_chorrera", 60, "corredor_oeste"),
    ("5_de_mayo", "la_chorrera", 65, "corredor_oeste"),
    ("los_andes", "chilibre", 25, "corredor_norte"),
]

# Corregimiento -> (nombre, distrito, nodo de acceso, sistema, minutos de acceso estimados).
# Nodo None => sin evidencia de nodo troncal que lo sirva: sus pares quedan `desconocido`.
# Nombres y distritos verificados con la cartografía oficial (División Política de Panamá
# 2024, geoportal del MiAmbiente). Ver datos/FUENTES_TRANSPORTE.md.
ZONAS: dict[str, tuple[str, str, str | None, str | None, float | None]] = {
    # Distrito de Panamá
    "ancon": ("Ancón", "Panamá", "albrook", "metro", 6),
    "bella_vista": ("Bella Vista", "Panamá", "via_argentina", "metro", 6),
    "calidonia": ("Calidonia", "Panamá", "5_de_mayo", "metro", 5),
    "betania": ("Betania", "Panamá", "fernandez_de_cordoba", "metro", 8),
    "san_francisco": ("San Francisco", "Panamá", "fernandez_de_cordoba", "metro", 7),
    "juan_diaz": ("Juan Díaz", "Panamá", "villa_lucre", "metro", 12),
    "tocumen": ("Tocumen", "Panamá", "altos_de_tocumen", "metro", 10),
    "veinticuatro_diciembre": ("24 de Diciembre", "Panamá", "24_de_diciembre", "metro", 8),
    "las_cumbres": ("Las Cumbres", "Panamá", "chilibre", "bus", 12),
    # Distrito de San Miguelito
    "amelia_denis_icaza": ("Amelia Denis de Icaza", "San Miguelito", "san_miguelito", "metro", 9),
    "belisario_porras": ("Belisario Porras", "San Miguelito", "pan_de_azucar", "metro", 10),
    "jose_domingo_espinar": ("José Domingo Espinar", "San Miguelito", "pan_de_azucar", "metro", 12),
    "rufina_alfaro": ("Rufina Alfaro", "San Miguelito", "cerro_viento", "metro", 13),
    "belisario_frias": ("Belisario Frías", "San Miguelito", "san_miguelito", "metro", 12),
    "omar_torrijos": ("Omar Torrijos", "San Miguelito", None, None, None),
    # Distrito de La Chorrera (Panamá Oeste)
    "barrio_colon": ("Barrio Colón", "La Chorrera", "la_chorrera", "bus", 6),
    "barrio_balboa": ("Barrio Balboa", "La Chorrera", "la_chorrera", "bus", 8),
    "guadalupe": ("Guadalupe", "La Chorrera", "la_chorrera", "bus", 14),
    # Distrito de Arraiján (Panamá Oeste)
    "arraijan": ("Arraiján cabecera", "Arraiján", "arraijan", "bus", 6),
    "vista_alegre": ("Vista Alegre", "Arraiján", "arraijan", "bus", 14),
    "burunga": ("Burunga", "Arraiján", "arraijan", "bus", 16),
}

# Tarifas oficiales (B/. por viaje) y su nivel de respaldo.
TARIFA_METRO = 0.35          # oficial
TARIFA_METRO_DOS_LINEAS = 0.85  # dato de terceros (parcial); supuesto de transbordo interno
TARIFA_CORREDOR = 0.75       # oficial (MiBus)
TARIFA_BUS_LOCAL = 0.25      # troncal oficial, usado como supuesto de viaje local

COLUMNAS = [
    "origen", "destino", "nombre_origen", "nombre_destino", "distrito_origen",
    "distrito_destino", "modo", "ruta", "tiempo_min", "tarifa_usd", "transbordos",
    "franja_horaria", "tipo_dato", "confianza", "fuente_url", "fuente_tiempo",
    "fecha_consulta", "nota",
]

NOTA_DESCONOCIDO = ("Sin datos verificables de transporte para esta zona: no hay evidencia "
                    "de un nodo troncal que la sirva. Se deja como desconocido (ver "
                    "datos/FUENTES_TRANSPORTE.md) en lugar de inventar tiempos o tarifas.")


def _redondear(x: float) -> int:
    return int(math.floor(x + 0.5))


def _grafo() -> dict[tuple[str, str], list[tuple[tuple[str, str], float, str, str | None]]]:
    """Grafo {(nodo, sistema): [(vecino, minutos, tipo, etiqueta), ...]}."""
    g: dict[tuple[str, str], list] = {}
    for a, b, minutos, etiqueta in ARISTAS_BUS:
        _arista(g, (a, "bus"), (b, "bus"), float(minutos), "bus", etiqueta)
    for linea, nodos in (("L1", NODOS_L1), ("L2", NODOS_L2)):
        for a, b in zip(nodos, nodos[1:]):
            _arista(g, (a, "metro"), (b, "metro"), SEG_METRO, "metro", linea)
    for nodo in ("albrook", "5_de_mayo", "los_andes"):
        _arista(g, (nodo, "bus"), (nodo, "metro"), TRANSBORDO_BUS_METRO, "transbordo", None)
    return g


def _arista(g, a, b, minutos, tipo, etiqueta) -> None:
    g.setdefault(a, []).append((b, minutos, tipo, etiqueta))
    g.setdefault(b, []).append((a, minutos, tipo, etiqueta))


def _ruta_mas_corta(g, inicio, fin):
    """Dijkstra. Devuelve (minutos, tipos, etiquetas, transbordos) o None."""
    import heapq

    dist = {inicio: 0.0}
    prev: dict = {}
    cola = [(0.0, inicio)]
    while cola:
        d, nodo = heapq.heappop(cola)
        if d > dist.get(nodo, math.inf):
            continue
        if nodo == fin:
            break
        for vecino, minutos, tipo, etiqueta in g.get(nodo, []):
            nd = d + minutos
            if nd < dist.get(vecino, math.inf):
                dist[vecino] = nd
                prev[vecino] = (nodo, tipo, etiqueta)
                heapq.heappush(cola, (nd, vecino))
    if fin not in dist:
        return None
    tipos: list[str] = []
    etiquetas: list[str] = []
    cursor = fin
    while cursor in prev:
        anterior, tipo, etiqueta = prev[cursor]
        tipos.append(tipo)
        if etiqueta:
            etiquetas.append(etiqueta)
        cursor = anterior
    tipos.reverse()
    etiquetas.reverse()
    return dist[fin], tipos, etiquetas, tipos.count("transbordo")


def _tarifa(tipos: list[str], etiquetas: list[str]) -> tuple[float, str, str, str]:
    """(tarifa_usd, modo, confianza, ruta)."""
    lineas = {e for e in etiquetas if e in ("L1", "L2")}
    corredores = sorted(e for e in etiquetas if e.startswith("corredor_"))
    usa_metro = "metro" in tipos
    usa_bus = "bus" in tipos
    if usa_metro and not usa_bus:
        if len(lineas) <= 1:
            return TARIFA_METRO, "metro", "alta", "+".join(sorted(lineas)) or "L1"
        return TARIFA_METRO_DOS_LINEAS, "metro", "media", "+".join(sorted(lineas))
    if usa_bus and not usa_metro:
        return TARIFA_CORREDOR, "corredor", "media", "+".join(corredores) or "corredor"
    if usa_metro and usa_bus:
        ruta = "+".join(sorted(lineas) + corredores)
        return TARIFA_METRO + TARIFA_CORREDOR, "corredor+metro", "baja", ruta
    return TARIFA_BUS_LOCAL, "bus_local", "baja", "local"


def _fuentes(modo: str) -> tuple[str, str]:
    if modo == "metro":
        return FUENTE_METRO, FUENTE_METRO_TIEMPO
    if modo in ("corredor", "bus_local"):
        return FUENTE_MIBUS, ""
    return FUENTE_METRO, FUENTE_METRO_TIEMPO   # corredor+metro


def _nota(modo: str, confianza: str) -> str:
    base = "Tiempo estimado con el modelo propio (ver datos/FUENTES_TRANSPORTE.md); no es un dato oficial por par."
    if modo == "corredor+metro":
        return base + " Tarifa combinada supuesta (corredor+metro)."
    if modo == "bus_local":
        return base + " Viaje local supuesto con tarifa troncal."
    if confianza == "media" and modo == "metro":
        return base + " Tarifa de dos líneas: dato de terceros, sujeta a verificación."
    return base


def _fila_desconocida(origen, destino, nom_o, nom_d, dist_o, dist_d, franja) -> dict:
    return {
        "origen": origen,
        "destino": destino,
        "nombre_origen": nom_o,
        "nombre_destino": nom_d,
        "distrito_origen": dist_o,
        "distrito_destino": dist_d,
        "modo": "desconocido",
        "ruta": "",
        "tiempo_min": "",
        "tarifa_usd": "",
        "transbordos": "",
        "franja_horaria": franja,
        "tipo_dato": "desconocido",
        "confianza": "desconocida",
        "fuente_url": "",
        "fuente_tiempo": "",
        "fecha_consulta": "",
        "nota": NOTA_DESCONOCIDO,
    }


def filas() -> list[dict]:
    g = _grafo()
    resultado: list[dict] = []
    for origen, (nom_o, dist_o, nodo_o, sis_o, acc_o) in ZONAS.items():
        for destino, (nom_d, dist_d, nodo_d, sis_d, acc_d) in ZONAS.items():
            if origen == destino:
                continue
            if nodo_o is None or nodo_d is None:
                for franja in ("pico", "valle"):
                    resultado.append(_fila_desconocida(
                        origen, destino, nom_o, nom_d, dist_o, dist_d, franja))
                continue
            tramo = _ruta_mas_corta(g, (nodo_o, sis_o), (nodo_d, sis_d))
            if tramo is None:
                raise RuntimeError(f"sin ruta entre {origen} y {destino}")
            minutos, tipos, etiquetas, transbordos = tramo
            base = acc_o + minutos + acc_d
            tarifa, modo, confianza, ruta = _tarifa(tipos, etiquetas)
            fuente_url, fuente_tiempo = _fuentes(modo)
            for franja, valor in (("pico", base * FACTOR_PICO), ("valle", base)):
                resultado.append({
                    "origen": origen,
                    "destino": destino,
                    "nombre_origen": nom_o,
                    "nombre_destino": nom_d,
                    "distrito_origen": dist_o,
                    "distrito_destino": dist_d,
                    "modo": modo,
                    "ruta": ruta,
                    "tiempo_min": _redondear(valor),
                    "tarifa_usd": f"{tarifa:.2f}",
                    "transbordos": transbordos,
                    "franja_horaria": franja,
                    "tipo_dato": "estimado",
                    "confianza": confianza,
                    "fuente_url": fuente_url,
                    "fuente_tiempo": fuente_tiempo,
                    "fecha_consulta": FECHA_CONSULTA,
                    "nota": _nota(modo, confianza),
                })
    return resultado


def escribir(ruta: Path) -> int:
    datos = filas()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, lineterminator="\n")
        w.writeheader()
        w.writerows(datos)
    return len(datos)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--salida", default=str(SALIDA_POR_DEFECTO))
    args = p.parse_args()
    ruta = Path(args.salida)
    n = escribir(ruta)
    pares = len(ZONAS) * (len(ZONAS) - 1)
    distritos: dict[str, int] = {}
    sin_nodo = [z for z, v in ZONAS.items() if v[2] is None]
    for _, dist, *_ in ZONAS.values():
        distritos[dist] = distritos.get(dist, 0) + 1
    print(f"Escrito {ruta} con {n} filas ({pares} pares dirigidos x 2 franjas).")
    print(f"Zonas: {len(ZONAS)} {distritos}. Sin nodo (desconocido): {sin_nodo or 'ninguna'}.")
    print("Tiempos ESTIMADOS; tarifas basadas en tarifas oficiales; filas desconocidas sin inventar.")


if __name__ == "__main__":
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    main()
