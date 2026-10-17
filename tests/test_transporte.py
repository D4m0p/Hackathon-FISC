"""Valida la tabla de transporte (`datos/transporte.csv`) y su cargador.

Comprueba el esquema, los campos obligatorios, tarifas no negativas, tiempos positivos
cuando existen, filas desconocidas (sin datos), ausencia de duplicados, URLs de fuentes,
la compatibilidad con el contrato `Traslado`, el mecanismo `sin_datos`, la cobertura y
que la generación sea reproducible.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CSV = RAIZ / "datos" / "transporte.csv"
GENERADOR = RAIZ / "datos" / "construir_transporte.py"
CARGADOR = RAIZ / "datos" / "cargar_transporte.py"
FUENTES = RAIZ / "datos" / "FUENTES_TRANSPORTE.md"

if str(RAIZ / "datos") not in sys.path:
    sys.path.insert(0, str(RAIZ / "datos"))

from contrato.modelos import Traslado  # noqa: E402

COLUMNAS = {
    "origen", "destino", "nombre_origen", "nombre_destino", "distrito_origen",
    "distrito_destino", "modo", "ruta", "tiempo_min", "tarifa_usd", "transbordos",
    "franja_horaria", "fuente_url", "fecha_consulta", "confianza", "tipo_dato",
}
FRANJAS = {"pico", "valle"}
CONFIANZAS = {"alta", "media", "baja", "desconocida"}
TIPOS = {"estimado", "desconocido"}
MODOS = {"metro", "corredor", "corredor+metro", "bus_local", "desconocido"}
DISTRITOS = {"Panamá", "San Miguelito", "La Chorrera", "Arraiján"}
DOMINIOS = ("https://elmetrodepanama.com/", "https://www.mibus.com.pa/")
PATRON_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

ZONAS_ESPERADAS = 21
FILAS_ESPERADAS = ZONAS_ESPERADAS * (ZONAS_ESPERADAS - 1) * 2


def _leer() -> list[dict[str, str]]:
    with CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _conocidas(filas) -> list[dict[str, str]]:
    return [f for f in filas if f["tipo_dato"] == "estimado"]


def test_el_csv_existe_y_tiene_las_columnas_obligatorias():
    assert CSV.exists(), "falta datos/transporte.csv; corre datos/construir_transporte.py"
    with CSV.open(encoding="utf-8", newline="") as f:
        campos = set(csv.DictReader(f).fieldnames or [])
    assert COLUMNAS <= campos, sorted(COLUMNAS - campos)


def test_campos_obligatorios_bien_formados_en_toda_fila():
    for fila in _leer():
        assert PATRON_ID.match(fila["origen"]), fila["origen"]
        assert PATRON_ID.match(fila["destino"]), fila["destino"]
        assert fila["origen"] != fila["destino"], fila
        assert fila["franja_horaria"] in FRANJAS, fila
        assert fila["confianza"] in CONFIANZAS, fila
        assert fila["tipo_dato"] in TIPOS, fila
        assert fila["modo"] in MODOS, fila
        assert fila["distrito_origen"] in DISTRITOS, fila
        assert fila["distrito_destino"] in DISTRITOS, fila
        assert fila["nombre_origen"].strip() and fila["nombre_destino"].strip(), fila


def test_filas_con_datos_tienen_tiempo_tarifa_fuente_y_fecha():
    filas = _conocidas(_leer())
    assert filas, "se esperaban pares con datos estimados"
    for fila in filas:
        assert 0 < int(fila["tiempo_min"]) <= 1440, f"tiempo fuera de rango: {fila}"
        assert float(fila["tarifa_usd"]) >= 0, f"tarifa negativa: {fila}"
        assert int(fila["transbordos"]) >= 0, f"transbordos negativos: {fila}"
        assert fila["fuente_url"].startswith(DOMINIOS), f"fuente no oficial: {fila}"
        if fila["fuente_tiempo"]:
            assert fila["fuente_tiempo"].startswith(DOMINIOS), fila["fuente_tiempo"]
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", fila["fecha_consulta"]), fila


def test_filas_desconocidas_no_inventan_tiempo_ni_tarifa():
    desconocidas = [f for f in _leer() if f["tipo_dato"] == "desconocido"]
    assert desconocidas, "se esperaba al menos una zona sin nodo (desconocido)"
    for fila in desconocidas:
        assert fila["tiempo_min"] == "", fila
        assert fila["tarifa_usd"] == "", fila
        assert fila["transbordos"] == "", fila
        assert fila["fuente_url"] == "", fila
        assert fila["fecha_consulta"] == "", fila
        assert fila["modo"] == "desconocido", fila
        assert fila["nota"].strip(), fila


def test_tipos_de_tiempo_no_se_declaran_oficiales():
    for fila in _conocidas(_leer()):
        assert fila["tipo_dato"] == "estimado", \
            f"un tiempo por par no puede ser oficial en esta tabla: {fila}"


def test_sin_duplicados_por_par_y_franja():
    vistos = [(f["origen"], f["destino"], f["franja_horaria"]) for f in _leer()]
    assert len(vistos) == len(set(vistos)), "hay filas duplicadas"


def test_cada_par_tiene_pico_y_valle_y_pico_no_es_menor():
    por_par: dict[tuple[str, str], dict[str, int]] = {}
    for fila in _conocidas(_leer()):
        por_par.setdefault((fila["origen"], fila["destino"]), {})[fila["franja_horaria"]] = \
            int(fila["tiempo_min"])
    for par, franjas in por_par.items():
        assert set(franjas) == FRANJAS, f"{par} no tiene ambas franjas"
        assert franjas["pico"] >= franjas["valle"], f"{par}: pico < valle"


def test_cobertura_de_zonas_dirigidas_y_sin_autopares():
    filas = _leer()
    zonas = {f["origen"] for f in filas} | {f["destino"] for f in filas}
    assert len(zonas) == ZONAS_ESPERADAS, sorted(zonas)
    assert len(filas) == FILAS_ESPERADAS, len(filas)
    pares = {(f["origen"], f["destino"]) for f in filas}
    assert len(pares) == ZONAS_ESPERADAS * (ZONAS_ESPERADAS - 1)
    for o in zonas:
        assert o not in {f["destino"] for f in filas if f["origen"] == o}
        assert {f["destino"] for f in filas if f["origen"] == o} == zonas - {o}


def test_representacion_por_distrito():
    zonas: dict[str, str] = {}
    for fila in _leer():
        zonas[fila["origen"]] = fila["distrito_origen"]
    por_distrito: dict[str, int] = {}
    for dist in zonas.values():
        por_distrito[dist] = por_distrito.get(dist, 0) + 1
    assert por_distrito.get("Panamá") == 9, por_distrito
    assert por_distrito.get("San Miguelito") == 6, por_distrito
    assert por_distrito.get("La Chorrera") == 3, por_distrito
    assert por_distrito.get("Arraiján") == 3, por_distrito


def test_san_francisco_es_zona_con_ida_y_vuelta_a_las_otras_veinte():
    zonas = {f["origen"] for f in _leer()}
    assert "san_francisco" in zonas
    assert len(zonas) == ZONAS_ESPERADAS
    pares = {(f["origen"], f["destino"], f["franja_horaria"]) for f in _leer()}
    for otra in zonas - {"san_francisco"}:
        for franja in FRANJAS:
            assert ("san_francisco", otra, franja) in pares, (otra, franja)
            assert (otra, "san_francisco", franja) in pares, (otra, franja)


def test_san_francisco_tiene_datos_estimados_solo_donde_corresponde():
    filas = [f for f in _leer() if "san_francisco" in (f["origen"], f["destino"])]
    con_datos = [f for f in filas if f["tipo_dato"] == "estimado"]
    sin_datos = [f for f in filas if f["tipo_dato"] == "desconocido"]
    assert len(filas) == 80
    assert len(con_datos) == 76 and len(sin_datos) == 4
    # San Francisco tiene nodo (Fernández de Córdoba), así que solo queda sin datos
    # frente a la zona sin nodo (Omar Torrijos), en ambos sentidos y franjas.
    assert {frozenset((f["origen"], f["destino"])) for f in sin_datos} == \
        {frozenset(("san_francisco", "omar_torrijos"))}
    for f in con_datos:
        assert 0 < int(f["tiempo_min"]) <= 1440, f
        assert float(f["tarifa_usd"]) >= 0, f
    for f in sin_datos:
        assert f["tiempo_min"] == "" and f["tarifa_usd"] == "" and f["modo"] == "desconocido"


def test_es_compatible_con_el_contrato_traslado():
    r = subprocess.run([sys.executable, str(CARGADOR), "--json", "--franja", "valle"],
                       capture_output=True, text=True, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    traslados = json.loads(r.stdout)
    assert traslados, "el cargador no devolvió traslados"
    for t in traslados:
        Traslado(**t)   # lanza si no cumple el contrato


def test_el_cargador_usa_la_franja_pedida_y_omite_desconocidos():
    import cargar_transporte

    def minutos(franja: str):
        return {(t.origen, t.destino): t.minutos
                for t in cargar_transporte.cargar_traslados(CSV, franja)}

    pico, valle = minutos("pico"), minutos("valle")
    assert pico.keys() == valle.keys()
    assert all(pico[k] >= valle[k] for k in valle)
    zonas = {f["origen"] for f in _leer()}
    assert not any("omar_torrijos" in par for par in valle), "una pareja desconocida no debe cargarse"


def test_una_zona_sin_datos_llega_al_mecanismo_sin_datos():
    import cargar_transporte
    from agentes.matching import MatrizTraslados

    matriz = MatrizTraslados(cargar_transporte.cargar_traslados(CSV, "valle"))
    assert matriz.viaje("ancon", "omar_torrijos") is None
    assert matriz.viaje("ancon", "bella_vista") is not None


def _ids_del_stack_demo() -> set[str]:
    """Corregimientos que usan los datos de demostración (jóvenes, vacantes, cursos y traslados)."""
    ids: set[str] = set()
    for p in (RAIZ / "scripts" / "demo" / "datos_demo.json",
              RAIZ / "datos" / "demo_muestra" / "datos_muestra.json"):
        datos = json.loads(p.read_text(encoding="utf-8"))
        for r in datos.get("jovenes", []):
            ids.add(r["joven"]["corregimiento"])
        for v in datos.get("vacantes", []):
            ids.add(v["corregimiento"])
        for c in datos.get("cursos", []):
            ids.add(c["corregimiento"])
        for t in datos.get("traslados", []):
            ids.update((t["origen"], t["destino"]))
    return ids


def test_cobertura_de_los_ids_de_la_demo_queda_documentada():
    import cargar_transporte

    ids = _ids_del_stack_demo()
    cob = cargar_transporte.cobertura(sorted(ids))
    assert set(cob["cubiertos"]) | set(cob["alias"]) | set(cob["faltantes"]) == ids, \
        "todo id del stack de demo debe clasificarse como cubierto, alias o faltante"
    assert set(cob["cubiertos"]) >= {"arraijan", "bella_vista", "betania", "juan_diaz",
                                     "san_francisco", "tocumen"}
    assert cob["alias"] == {"la_chorrera": "barrio_colon"}, cob["alias"]
    assert set(cob["faltantes"]) == {"san_miguelito"}, cob["faltantes"]


def test_los_alias_de_demo_conectan_la_chorrera_sin_tocar_el_matching():
    import cargar_transporte
    from agentes.matching import MatrizTraslados

    base = MatrizTraslados(cargar_transporte.cargar_traslados(CSV, "valle"))
    assert base.viaje("la_chorrera", "bella_vista") is None, \
        "el id antiguo no está en la tabla: por defecto queda en `sin_datos`"

    con_alias = MatrizTraslados(cargar_transporte.cargar_para_demo(CSV, "valle"))
    assert con_alias.viaje("la_chorrera", "bella_vista") is not None
    assert con_alias.viaje("juan_diaz", "la_chorrera") is not None
    assert con_alias.viaje("la_chorrera", "bella_vista").minutos > 0
    # san_francisco ya es zona de la tabla: ahora sí tiene par con Bella Vista
    assert con_alias.viaje("san_francisco", "bella_vista") is not None
    # sin equivalente claro no se inventa: san_miguelito sigue en `sin_datos`
    assert con_alias.viaje("san_miguelito", "bella_vista") is None


def _almacen():
    from orquestador.almacen import Almacen
    return Almacen(":memory:")


def test_complementar_conserva_los_traslados_de_la_demo():
    import cargar_transporte

    almacen = _almacen()
    demo = [Traslado(origen="bella_vista", destino="juan_diaz", minutos=999, costo=9.99),
            Traslado(origen="la_chorrera", destino="bella_vista", minutos=70, costo=1.6)]
    almacen.guardar_traslados(demo)
    cargar_transporte.cargar_en(almacen, CSV, "valle", complementar=True)

    original = {(t.origen, t.destino): t for t in demo}
    guardados = {(t.origen, t.destino): t for t in almacen.traslados()}
    for par, t in original.items():
        assert guardados[par] == t, f"se perdió el traslado original de la demo en {par}"


def test_complementar_agrega_pares_nuevos_de_la_tabla():
    import cargar_transporte

    almacen = _almacen()
    almacen.guardar_traslados([Traslado(origen="la_chorrera", destino="bella_vista",
                                       minutos=70, costo=1.6)])
    antes = {(t.origen, t.destino) for t in almacen.traslados()}
    cargar_transporte.cargar_en(almacen, CSV, "valle", complementar=True)
    despues = {(t.origen, t.destino) for t in almacen.traslados()}

    assert antes < despues, "la tabla debe añadir pares nuevos"
    assert ("ancon", "bella_vista") in despues - antes
    assert ("barrio_colon", "bella_vista") in despues - antes
    assert ("la_chorrera", "bella_vista") in despues  # el original de la demo se conserva


def test_pares_repetidos_mantienen_prioridad_de_la_demo():
    import cargar_transporte

    almacen = _almacen()
    demo = Traslado(origen="bella_vista", destino="juan_diaz", minutos=11, costo=0.11)
    almacen.guardar_traslados([demo])
    cargar_transporte.cargar_en(almacen, CSV, "valle", complementar=True)

    guardado = {(t.origen, t.destino): t for t in almacen.traslados()}[("bella_vista", "juan_diaz")]
    assert guardado == demo, "un par repetido debe conservar el valor curado de la demo"


def test_complementar_es_idempotente_y_sin_duplicados():
    import cargar_transporte

    almacen = _almacen()
    almacen.guardar_traslados([Traslado(origen="la_chorrera", destino="bella_vista",
                                       minutos=70, costo=1.6)])
    total1 = cargar_transporte.cargar_en(almacen, CSV, "valle", complementar=True)
    lista1 = almacen.traslados()
    total2 = cargar_transporte.cargar_en(almacen, CSV, "valle", complementar=True)
    lista2 = almacen.traslados()

    assert total1 == total2 == len(lista2) == len({(t.origen, t.destino) for t in lista2})
    assert [(t.origen, t.destino, t.minutos, t.costo) for t in lista1] == \
           [(t.origen, t.destino, t.minutos, t.costo) for t in lista2], \
        "repetir la integración no debe cambiar ni duplicar los traslados"


def test_los_ids_sin_correspondencia_no_reciben_datos_inventados():
    import cargar_transporte
    from agentes.matching import MatrizTraslados

    almacen = _almacen()
    cargar_transporte.cargar_en(almacen, CSV, "valle", complementar=True)
    pares = {(t.origen, t.destino) for t in almacen.traslados()}
    # san_miguelito es un DISTRITO en la tabla (6 corregimientos), no un corregimiento:
    # no se le asignan pares propios ni se inventan datos.
    assert not any("san_miguelito" in p for p in pares)

    matriz = MatrizTraslados(almacen.traslados())
    assert matriz.viaje("san_miguelito", "bella_vista") is None


def test_la_integracion_conserva_los_28_traslados_de_la_demo():
    import cargar_transporte

    demo = json.loads((RAIZ / "scripts" / "demo" / "datos_demo.json").read_text(encoding="utf-8"))
    curados = {(t["origen"], t["destino"]): t for t in demo["traslados"]}
    assert len(curados) == 28

    almacen = _almacen()
    almacen.guardar_traslados([Traslado(**t) for t in demo["traslados"]])
    cargar_transporte.cargar_en(almacen, CSV, "valle", complementar=True)

    guardados = {(t.origen, t.destino): t for t in almacen.traslados()}
    for par, t in curados.items():
        assert guardados[par].minutos == t["minutos"], par
        assert guardados[par].costo == t["costo"], par
    # y San Francisco ya aporta pares nuevos que la demo no tenía
    assert [p for p in guardados if "san_francisco" in p and p not in curados], \
        "San Francisco debe sumar trayectos nuevos"


def test_sembrar_transporte_conserva_las_cinco_asignaciones_y_sin_duplicados():
    import sembrar_transporte

    orq, _, resumen, _ = sembrar_transporte.sembrar(":memory:", con_matching=True)
    assert resumen["asignaciones"] == ["j01→v01", "j03→v02", "j04→v06", "j06→v03", "j10→v01"]
    assert resumen["traslados_agregados"] > 0
    traslados = orq.almacen.traslados()
    assert len(traslados) == len({(t.origen, t.destino) for t in traslados}), "hay duplicados"


def test_la_generacion_es_reproducible(tmp_path):
    salida = tmp_path / "transporte.csv"
    subprocess.run([sys.executable, str(GENERADOR), "--salida", str(salida)],
                   check=True, capture_output=True)
    assert salida.read_bytes() == CSV.read_bytes(), \
        "datos/transporte.csv no coincide con una corrida limpia; regenéralo"


def test_las_fuentes_documentan_lo_verificado_estimado_y_desconocido():
    assert FUENTES.exists(), "falta datos/FUENTES_TRANSPORTE.md"
    texto = FUENTES.read_text(encoding="utf-8").lower()
    assert "estimad" in texto and "pendiente" in texto and "desconocid" in texto
    assert "declarar cobertura completa" in texto, \
        "debe advertir que no se declara cobertura completa"
    assert "oficial" in texto
