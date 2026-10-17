"""Valida los datos de muestra generados a partir de los CSV de investigación.

Comprueba el contrato (`Vacante`/`Curso`), la trazabilidad con el origen, el
manejo de campos ausentes y la reproducibilidad de la conversión.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from contrato.modelos import Curso, Vacante

RAIZ = Path(__file__).resolve().parent.parent
CONVERSOR = RAIZ / "datos" / "normalizar_demo.py"
DEMO = RAIZ / "datos" / "demo"
CSV_OFERTAS = RAIZ / "datos" / "ofertas_empleo.csv"
CSV_CURSOS = RAIZ / "datos" / "cursos.csv"

ARCHIVOS = ["vacantes_demo.json", "cursos_demo.json", "exclusiones.json"]
REQ_VACANTE = {"id", "empresa_id", "titulo", "corregimiento", "turnos", "salario_mensual"}
REQ_CURSO = {"id", "centro", "nombre", "corregimiento", "turnos", "sesiones_por_semana",
             "semanas", "cupos_disponibles", "habilidades_otorgadas"}


def _leer(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _ids_csv(ruta: Path) -> list[str]:
    with ruta.open(encoding="utf-8", newline="") as f:
        return [r["id"] for r in csv.DictReader(f)]


def _correr(salida: Path) -> None:
    subprocess.run([sys.executable, str(CONVERSOR), "--salida", str(salida)],
                   check=True, capture_output=True)


def test_los_archivos_generados_existen():
    for nombre in ARCHIVOS:
        assert (DEMO / nombre).exists(), f"falta {nombre}; corre datos/normalizar_demo.py"


def test_registros_convertidos_validan_contra_el_contrato():
    vacantes = _leer(DEMO / "vacantes_demo.json")
    for r in vacantes["registros"]:
        Vacante(**r)   # lanza si no cumple el contrato
    cursos = _leer(DEMO / "cursos_demo.json")
    for r in cursos["registros"]:
        Curso(**r)


def test_conteos_cuadran_con_los_csv():
    ofertas, cursos = _leer(DEMO / "vacantes_demo.json"), _leer(DEMO / "cursos_demo.json")
    excl = _leer(DEMO / "exclusiones.json")
    assert ofertas["total_origen"] == len(_ids_csv(CSV_OFERTAS))
    assert cursos["total_origen"] == len(_ids_csv(CSV_CURSOS))
    assert ofertas["total_convertidos"] + ofertas["total_excluidos"] == ofertas["total_origen"]
    assert cursos["total_convertidos"] + cursos["total_excluidos"] == cursos["total_origen"]
    assert len(ofertas["registros"]) == ofertas["total_convertidos"]
    assert len(cursos["registros"]) == cursos["total_convertidos"]
    assert len(excl["ofertas"]) == ofertas["total_excluidos"]
    assert len(excl["cursos"]) == cursos["total_excluidos"]


def test_trazabilidad_cubre_todos_los_registros_de_origen():
    excl = _leer(DEMO / "exclusiones.json")
    ofertas, cursos = _leer(DEMO / "vacantes_demo.json"), _leer(DEMO / "cursos_demo.json")
    ids_conv_o = {r["id"] for r in ofertas["registros"]}
    ids_conv_c = {r["id"] for r in cursos["registros"]}
    ids_exc_o = {e["origen"]["id_origen"] for e in excl["ofertas"]}
    ids_exc_c = {e["origen"]["id_origen"] for e in excl["cursos"]}
    assert ids_conv_o | ids_exc_o == set(_ids_csv(CSV_OFERTAS))
    assert ids_conv_c | ids_exc_c == set(_ids_csv(CSV_CURSOS))
    assert ids_conv_o.isdisjoint(ids_exc_o) and ids_conv_c.isdisjoint(ids_exc_c)
    assert not (ids_conv_o & ids_exc_o) and not (ids_conv_c & ids_exc_c)


def test_exclusiones_tienen_motivo_y_campos_faltantes_coherentes():
    excl = _leer(DEMO / "exclusiones.json")
    for tipo, requeridos in (("ofertas", REQ_VACANTE), ("cursos", REQ_CURSO)):
        assert excl[tipo], f"se esperaban exclusiones en {tipo}"
        for e in excl[tipo]:
            assert e["motivo"].strip(), "una exclusión sin motivo"
            assert e["campos_faltantes"], "una exclusión sin campos faltantes"
            assert set(e["campos_faltantes"]) <= requeridos, e["campos_faltantes"]
            assert not (set(e["campos_faltantes"]) & set(e["campos_mapeados"]))
            assert e["origen"]["url"].startswith("http"), e["origen"]


def test_conversion_es_reproducible_y_coincide_con_lo_guardado(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _correr(a)
    _correr(b)
    for nombre in ARCHIVOS:
        bytes_a = (a / nombre).read_bytes()
        assert bytes_a == (b / nombre).read_bytes(), f"{nombre} no es determinístico"
        assert bytes_a == (DEMO / nombre).read_bytes(), \
            f"{nombre} guardado no coincide con una corrida limpia; regenéralo"


def test_ninguna_vacante_se_marca_como_activa():
    texto = (DEMO / "vacantes_demo.json").read_text(encoding="utf-8").lower()
    assert "no oportunidades activas confirmadas" in texto


pytestmark = pytest.mark.skipif(not CONVERSOR.exists(), reason="falta el conversor")
