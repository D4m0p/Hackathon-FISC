"""Valida la MUESTRA SINTÉTICA (`datos/demo_muestra/datos_muestra.json`).

Comprueba que es coherente con el contrato, que está rotulada como ficticia, que no
se mezcla con los datos de investigación y que el flujo carga de punta a punta.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from contrato.modelos import Curso, DatosPersonales, Joven, Traslado, Turno, Vacante

RAIZ = Path(__file__).resolve().parent.parent
MUESTRA = RAIZ / "datos" / "demo_muestra" / "datos_muestra.json"
CARGADOR = RAIZ / "datos" / "cargar_muestra.py"
CSV_OFERTAS = RAIZ / "datos" / "ofertas_empleo.csv"
CSV_CURSOS = RAIZ / "datos" / "cursos.csv"

DATOS = json.loads(MUESTRA.read_text(encoding="utf-8"))


def _ids_csv(ruta: Path) -> set[str]:
    with ruta.open(encoding="utf-8", newline="") as f:
        return {r["id"] for r in csv.DictReader(f)}


def _codigos(valor) -> set[str]:
    if isinstance(valor, list):
        return {x for x in valor if isinstance(x, str)}
    texto = (valor or "").strip()
    return {c for c in texto.split(";") if c} if texto else set()


def test_la_muestra_esta_rotulada_como_ficticia():
    assert "SINTÉTICA" in DATOS["_nota"].upper()
    assert "fictic" in DATOS["_nota"].lower()
    for v in DATOS["vacantes"]:
        assert v["empresa_id"].startswith("e_sint_"), v["id"]
        assert v["id"].startswith("v_sint_") or "_sint_" in v["id"]
    for c in DATOS["cursos"]:
        assert "_sint_" in c["id"]
        assert c["centro"] == "Centro Demo de Formación"


def test_todos_los_registros_validan_contra_el_contrato():
    for t in DATOS["traslados"]:
        Traslado(**t)
    for v in DATOS["vacantes"]:
        Vacante(**v)
    for c in DATOS["cursos"]:
        Curso(**c)
    for r in DATOS["jovenes"]:
        Joven(**r["joven"])
        DatosPersonales(**r["datos"])


def test_no_se_mezcla_con_los_datos_de_investigacion():
    ids_of = _ids_csv(CSV_OFERTAS)
    ids_cu = _ids_csv(CSV_CURSOS)
    for v in DATOS["vacantes"]:
        assert v["id"] not in ids_of
        assert not (v.get("texto_original") or "").startswith("http")
    for c in DATOS["cursos"]:
        assert c["id"] not in ids_cu
    crudo = MUESTRA.read_text(encoding="utf-8")
    assert '"url"' not in crudo, "una muestra no debe traer URLs de origen"


def test_integridad_referencial_de_la_muestra():
    taxonomia = {h["codigo"] for h in DATOS["habilidades"]}
    corregimientos = {t["origen"] for t in DATOS["traslados"]} | {t["destino"] for t in DATOS["traslados"]}
    turnos = {t.value for t in Turno}

    for v in DATOS["vacantes"]:
        assert v["corregimiento"] in corregimientos, v["id"]
        assert set(v["turnos"]) <= turnos, v["id"]
        assert {r["codigo"] for r in v["habilidades_requeridas"]} <= taxonomia, v["id"]
    for c in DATOS["cursos"]:
        assert c["corregimiento"] in corregimientos, c["id"]
        assert set(c["turnos"]) <= turnos, c["id"]
        assert {h["codigo"] for h in c["habilidades_otorgadas"]} <= taxonomia, c["id"]

    ids_jovenes = {r["joven"]["id"] for r in DATOS["jovenes"]}
    ids_vacantes = {v["id"] for v in DATOS["vacantes"]}
    for r in DATOS["jovenes"]:
        j = r["joven"]
        assert j["corregimiento"] in corregimientos, j["id"]
        assert set(j["disponibilidad"]) <= turnos, j["id"]
        assert {h["codigo"] for h in j["habilidades"]} <= taxonomia, j["id"]
    for d in DATOS["deslizamientos"]:
        assert d["joven_id"] in ids_jovenes and d["vacante_id"] in ids_vacantes, d
        assert d["actor"] in {"joven", "empresa"}, d


def test_el_flujo_carga_y_produce_resultados(tmp_path):
    if not CARGADOR.exists():
        pytest.skip("falta datos/cargar_muestra.py")
    base = tmp_path / "muestra.db"
    r = subprocess.run([sys.executable, str(CARGADOR), "--base", str(base),
                        "--reiniciar", "--matching"],
                       capture_output=True, text=True, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    salida = r.stdout
    assert "bloqueadas: []" in salida
    assert "j_sint_maria→v_sint_seguridad" in salida
    assert "plane" in salida and "j_sint_jose" in salida
