"""Endpoints que muestran el trabajo de los agentes: tendencias (Mercado) y contrafactuales (Auditor)."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agentes.auditor.contrafactual as contrafactual
from agentes.auditor import Auditor
from api.main import crear_app
from contrato.modelos import Desglose
from orquestador import Almacen, Orquestador

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from semilla_demo import DATOS, cargar  # noqa: E402


@pytest.fixture
def sistema():
    orq = Orquestador(Almacen(), auditor=Auditor())
    cargar(orq, json.loads(DATOS.read_text(encoding="utf-8")), con_matching=True)
    orq.almacen.guardar_credencial("t-ori", "orientador", None)
    orq.almacen.guardar_credencial("t-j01", "joven", "j01")
    return orq, TestClient(crear_app(orq))


# ---------- tendencias (agente de Mercado) ----------

def test_tendencias_por_zona_solo_con_vacantes_publicadas(sistema):
    orq, c = sistema
    r = c.get("/mercado/tendencias", params={"top": 3})            # público, sin token
    assert r.status_code == 200
    t = r.json()
    assert t["total_vacantes"] == 11                              # 12 en la demo, v10 bloqueada
    assert t["vacantes_por_zona"]["bella_vista"] == 1             # la recepcionista bloqueada no cuenta
    assert t["por_zona"]["arraijan"][0] == {"codigo": "atencion_cliente", "nombre": "Atención al cliente",
                                            "vacantes": 2}
    assert all(len(lista) <= 3 for lista in t["por_zona"].values())
    assert "ilustrativo" in t["nota"]


def test_tendencias_valida_el_parametro(sistema):
    _, c = sistema
    assert c.get("/mercado/tendencias", params={"top": 0}).status_code == 422


# ---------- contrafactual (Auditor) ----------

def test_contrafactual_muestra_que_el_lugar_no_mueve_habilidades(sistema):
    _, c = sistema
    d = c.get("/auditoria/contrafactual/j01", headers={"Authorization": "Bearer t-ori"}).json()
    assert d["veredicto"] == "sin_sesgo" and d["hallazgos"] == []
    assert not {"nombre", "genero", "edad"} & set(d["campos_que_ve_el_solver"])
    assert "DatosPersonales" in d["identidad"]
    fila = d["filas"][0]
    factibles = [v for v in fila["variantes"] if v["factible"]]
    assert factibles and all(v["habilidades_igual"] for v in factibles)
    assert all(v["componentes"]["habilidades"] == fila["original"]["habilidades"] for v in factibles)
    assert any(v["componentes"]["traslado"] != fila["original"]["traslado"] for v in factibles)
    assert any(not v["factible"] for v in fila["variantes"])       # lejos, deja de ser factible


def test_el_auditor_detecta_un_puntaje_sesgado_por_lugar(sistema, monkeypatch):
    orq, _ = sistema
    original = contrafactual.evaluar

    def sesgado(joven, vacante, matriz, pesos=None):
        d = original(joven, vacante, matriz, pesos)
        if isinstance(d, Desglose) and joven.corregimiento == "arraijan":
            return d.model_copy(update={"habilidades": d.habilidades / 2})
        return d

    monkeypatch.setattr(contrafactual, "evaluar", sesgado)
    d = orq.demostrar_contrafactual("j01")
    assert d.veredicto == "revisar" and d.hallazgos[0].regla == "contrafactual_corregimiento"
    assert any(v.habilidades_igual is False for f in d.filas for v in f.variantes)


def test_contrafactual_solo_para_el_orientador(sistema):
    _, c = sistema
    assert c.get("/auditoria/contrafactual/j01").status_code == 401
    assert c.get("/auditoria/contrafactual/j01", headers={"Authorization": "Bearer t-j01"}).status_code == 403
    assert c.get("/auditoria/contrafactual/nadie", headers={"Authorization": "Bearer t-ori"}).status_code == 404
