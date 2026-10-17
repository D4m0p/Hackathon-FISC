"""Obtiene un punto por corregimiento desde OpenStreetMap (Nominatim) y escribe
`datos/corregimientos.csv` con su fuente.

No inventa coordenadas: solo escribe lo que devuelve Nominatim. Si un corregimiento no
tiene una frontera administrativa que coincida con su distrito, si el punto cae fuera de la
zona esperada o si falla la consulta, queda FUERA del CSV y se lista al final para revisarlo.

Uso (desde la raíz del repositorio, con internet):
    python datos/obtener_corregimientos.py --contacto tu_correo@ejemplo.com
    python datos/obtener_corregimientos.py --contacto ... --seco     # no escribe el CSV
    python datos/obtener_corregimientos.py --contacto ... --forzar   # escribe aunque falten zonas

Política de Nominatim: máximo 1 petición por segundo y un User-Agent que identifique quién
consulta; por eso `--contacto` es obligatorio. Los datos son de OpenStreetMap (©
colaboradores de OpenStreetMap, licencia ODbL): ver `datos/FUENTES_CORREGIMIENTOS.md`.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

URL_BUSQUEDA = "https://nominatim.openstreetmap.org/search"
# Caja aproximada de las zonas de datos/transporte.csv (Panamá, San Miguelito, Arraiján, La Chorrera).
LAT = (8.75, 9.25)
LON = (-79.95, -79.20)
# "Panamá" es a la vez país, provincia y distrito: su nombre no identifica la ubicación.
DISTRITO_GENERICO = "panama"
# Nodos de tipo "lugar" aceptados como último recurso (nunca edificios, comercios ni vías).
TIPOS_NODO_LUGAR = {"city", "town", "village", "suburb", "neighbourhood", "quarter"}
COLUMNAS = ["codigo", "nombre", "distrito", "lat", "lon", "tipo_punto",
            "fuente_url", "fecha_consulta"]


def _raiz_repo() -> Path:
    """Carpeta que contiene `datos/transporte.csv`, esté el script donde esté."""
    aqui = Path(__file__).resolve()
    for base in aqui.parents:
        if (base / "datos" / "transporte.csv").exists():
            return base
    return aqui.parent


RAIZ = _raiz_repo()
TRANSPORTE = RAIZ / "datos" / "transporte.csv"
SALIDA = RAIZ / "datos" / "corregimientos.csv"


@dataclass
class Analisis:
    codigo: str
    nombre: str
    distrito: str
    consultas: list[str]
    consulta: str
    resultado: dict | None
    tipo_punto: str | None
    confianza: str | None
    motivo_confianza: str | None
    fuera: str | None


def sin_acentos(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto)
    return "".join(c for c in base if unicodedata.category(c) != "Mn").lower()


def componentes(display_name: str) -> list[str]:
    return [c.strip() for c in display_name.split(",") if c.strip()]


def es_frontera(r: dict) -> bool:
    return (r.get("osm_type") == "relation" and r.get("category") == "boundary"
            and r.get("type") == "administrative")


def es_nodo_lugar(r: dict) -> bool:
    return (r.get("osm_type") == "node" and r.get("category") == "place"
            and r.get("type") in TIPOS_NODO_LUGAR)


def distrito_coincide(partes_sin_pais: list[str], distrito: str) -> bool:
    """El componente debe ser igual al distrito o a "Distrito de <distrito>" (sin acentos).

    Así "Distrito de Panamá" casa con "Panamá", pero "Provincia de Panamá" y "Panamá Oeste"
    no. Se excluye el país fuera de esta función.
    """
    objetivo = sin_acentos(distrito)
    aceptados = {objetivo, f"distrito de {objetivo}"}
    return any(sin_acentos(p) in aceptados for p in partes_sin_pais)


def candidatas_frontera(resultados: list[dict], distrito: str) -> list[dict]:
    """Fronteras administrativas (relación OSM) cuyo texto nombra al distrito."""
    salida = []
    for r in resultados:
        if not es_frontera(r):
            continue
        partes = componentes(r.get("display_name", ""))
        if distrito_coincide(partes[:-1], distrito):  # sin el país
            salida.append(r)
    return salida


def candidatas_nodo(resultados: list[dict], distrito: str, nombre: str) -> list[dict]:
    """Nodos "lugar" cuyo primer tramo del texto es el corregimiento pedido y cuyo distrito
    coincide. Solo city/town/village/suburb/neighbourhood/quarter."""
    objetivo = sin_acentos(nombre_para_buscar(nombre))
    salida = []
    for r in resultados:
        if not es_nodo_lugar(r):
            continue
        partes = componentes(r.get("display_name", ""))
        if len(partes) < 2 or sin_acentos(partes[0]) != objetivo:
            continue
        if distrito_coincide(partes[:-1], distrito):  # sin el país
            salida.append(r)
    return salida


def nombre_para_buscar(nombre: str) -> str:
    return nombre.replace(" cabecera", "").strip()


def elegir(candidatas_: list[dict], nombre: str) -> dict:
    """Prefiere la frontera cuyo primer tramo es el propio corregimiento pedido; si ninguna
    coincide, toma la primera candidata (el orden de Nominatim ya es por relevancia)."""
    objetivo = sin_acentos(nombre_para_buscar(nombre))
    for r in candidatas_:
        partes = componentes(r.get("display_name", ""))
        if partes and sin_acentos(partes[0]) == objetivo:
            return r
    return candidatas_[0]


def confianza(distrito: str, n_candidatas: int) -> tuple[str, str]:
    if sin_acentos(distrito) == DISTRITO_GENERICO:
        return "REVISAR", (f'distrito genérico "Panamá" (país, provincia y distrito); '
                           f"{n_candidatas} frontera(s) candidata(s)")
    if n_candidatas > 1:
        return "REVISAR", f"{n_candidatas} fronteras candidatas"
    return "ALTA", "una sola frontera candidata y el distrito aparece sin el país"


def consultar(consulta: str, contacto: str) -> list[dict]:
    parametros = urllib.parse.urlencode({
        "q": consulta, "format": "jsonv2", "countrycodes": "pa",
        "limit": 5, "addressdetails": 1, "accept-language": "es"})
    peticion = urllib.request.Request(
        f"{URL_BUSQUEDA}?{parametros}",
        headers={"User-Agent": f"Hackathon-FISC-datos/1.0 ({contacto})"})
    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def _con_punto(codigo, nombre, distrito, intentadas, consulta, r, tipo_punto, nivel, motivo):
    lat, lon = float(r["lat"]), float(r["lon"])
    if not (LAT[0] <= lat <= LAT[1] and LON[0] <= lon <= LON[1]):
        return Analisis(codigo, nombre, distrito, intentadas, consulta, r, tipo_punto,
                        None, None, f"punto fuera de zona ({lat:.5f}, {lon:.5f})")
    return Analisis(codigo, nombre, distrito, intentadas, consulta, r, tipo_punto,
                    nivel, motivo, None)


def analizar(zona: tuple[str, str, str], consultar_fn, pausa: float = 0.0) -> Analisis:
    """Prueba las consultas en orden y se queda con la primera que dé candidato válido.

    Prioridad: frontera administrativa (relación) y, si no hay, un nodo "lugar" del corregimiento.
    """
    codigo, nombre, distrito = zona
    plan = [f"{nombre_para_buscar(nombre)}, {distrito}, Panamá",
            f"{nombre_para_buscar(nombre)}, Distrito de {distrito}, Panamá"]
    intentadas: list[str] = []
    for i, consulta in enumerate(plan):
        if i:
            time.sleep(pausa)  # pausa entre consultas de respaldo
        intentadas.append(consulta)
        try:
            resultados = consultar_fn(consulta)
        except Exception as e:  # red caída, límite, etc.: se reporta, no se inventa
            return Analisis(codigo, nombre, distrito, intentadas, consulta, None, None,
                            None, None, f"error de consulta: {e}")
        rels = candidatas_frontera(resultados, distrito)
        if rels:
            nivel, motivo = confianza(distrito, len(rels))
            return _con_punto(codigo, nombre, distrito, intentadas, consulta, elegir(rels, nombre),
                              "punto_osm", nivel, motivo)
        nodos = candidatas_nodo(resultados, distrito, nombre)
        if nodos:
            return _con_punto(codigo, nombre, distrito, intentadas, consulta, nodos[0],
                              "nodo_lugar_osm", "REVISAR",
                              "nodo de lugar (no es una frontera administrativa)")
    return Analisis(codigo, nombre, distrito, intentadas, plan[0], None, None, None, None,
                    "sin frontera administrativa que coincida con el distrito")


def zonas() -> list[tuple[str, str, str]]:
    with TRANSPORTE.open(encoding="utf-8", newline="") as f:
        vistas = {(x["origen"], x["nombre_origen"], x["distrito_origen"])
                  for x in csv.DictReader(f)}
    return sorted(vistas)


def imprimir(a: Analisis, indice: int, total: int) -> None:
    print(f"[{indice:>2}/{total}] {a.codigo}  ·  {a.nombre} (distrito: {a.distrito})")
    for j, q in enumerate(a.consultas, 1):
        marca = "   [usada]" if (a.resultado is not None and q == a.consulta) else ""
        print(f"        consulta{j}: {q}{marca}")
    if a.resultado is None:
        print("        elegido  : (ninguno)")
    else:
        print(f"        elegido  : {a.resultado.get('display_name', '')}")
        print(f"        fuente   : {a.resultado.get('osm_type')} "
              f"{a.resultado.get('osm_id')} · {a.tipo_punto} · "
              f"punto: {float(a.resultado['lat']):.6f}, {float(a.resultado['lon']):.6f}")
    if a.fuera:
        print(f"        FUERA    : {a.fuera}")
    else:
        print(f"        confianza: {a.confianza} ({a.motivo_confianza})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--contacto", required=True, help="correo o URL para el User-Agent")
    ap.add_argument("--pausa", type=float, default=1.2, help="segundos entre peticiones (>=1)")
    ap.add_argument("--seco", action="store_true", help="no escribe el CSV, solo imprime")
    ap.add_argument("--forzar", action="store_true",
                    help="escribe el CSV aunque falten zonas")
    args = ap.parse_args()
    if args.pausa < 1:
        ap.error("--pausa debe ser >= 1 para respetar la política de Nominatim")

    hoy = date.today().isoformat()
    lista = zonas()
    print(f"Consultando {len(lista)} zonas de {TRANSPORTE} ...\n")

    resultados, filas = [], []
    for i, zona in enumerate(lista, 1):
        a = analizar(zona, lambda c: consultar(c, args.contacto), pausa=args.pausa)
        imprimir(a, i, len(lista))
        print()
        resultados.append(a)
        if a.fuera is None:
            r = a.resultado
            filas.append({"codigo": a.codigo, "nombre": a.nombre, "distrito": a.distrito,
                          "lat": f"{float(r['lat']):.6f}", "lon": f"{float(r['lon']):.6f}",
                          "tipo_punto": a.tipo_punto,
                          "fuente_url": f"https://www.openstreetmap.org/{r['osm_type']}/{r['osm_id']}",
                          "fecha_consulta": hoy})
        time.sleep(args.pausa)

    altas = sum(1 for a in resultados if a.confianza == "ALTA")
    revisar = sum(1 for a in resultados if a.confianza == "REVISAR")
    fuera = [a for a in resultados if a.fuera]

    print("=" * 72)
    print(f"Resumen: total {len(resultados)} · OK (ALTA) {altas} · REVISAR {revisar} · "
          f"FUERA {len(fuera)}")
    if fuera:
        print(f"\nFUERA ({len(fuera)}): revisar a mano, no inventar")
        for a in fuera:
            print(f"  - {a.codigo}: {a.fuera}")

    if args.seco:
        print(f"\nModo seco: no se escribió {SALIDA}.")
    elif fuera and not args.forzar:
        print(f"\nFaltan {len(fuera)} zonas: no se sobrescribe {SALIDA} "
              f"(use --forzar para escribir de todos modos).")
    else:
        with SALIDA.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS)
            w.writeheader()
            w.writerows(filas)
        print(f"\nEscribí {len(filas)} corregimientos en {SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
