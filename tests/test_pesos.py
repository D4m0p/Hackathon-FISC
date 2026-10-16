from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agentes.matching import MatrizTraslados, evaluar
from contrato.modelos import Asignacion, Pesos, RequisitoHabilidad, Traslado
from orquestador import Almacen, ErrorDeFlujo, Orquestador
from tests.test_orquestador import AuditorFalso, MercadoFalso, NotificadorFalso, joven, vacante

VIERNES = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)
CERCANIA = Pesos(habilidades=0.2, traslado=0.7, salario=0.1)
MATRIZ = [Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0)]


def cerca_y_lejos():
    """'cerca' (mismo corregimiento) le pide una opcional que no tiene; 'lejos' encaja completa."""
    cerca = vacante("cerca", corregimiento="la_chorrera", habilidades_requeridas=[
        RequisitoHabilidad(codigo="caja"), RequisitoHabilidad(codigo="ventas", obligatoria=False)])
    lejos = vacante("lejos", corregimiento="arraijan")
    return cerca, lejos


# ---------- el modelo y sus guardrails ----------

def test_pesos_por_defecto_y_suma_uno():
    p = Pesos()
    assert (p.habilidades, p.traslado, p.salario) == (0.60, 0.25, 0.15)


@pytest.mark.parametrize("valores", [
    dict(habilidades=0.5, traslado=0.3, salario=0.3),     # suman 1.1
    dict(habilidades=0.9, traslado=0.05, salario=0.05),   # uno domina del todo
    dict(habilidades=0.0, traslado=0.6, salario=0.4),     # anula las habilidades
])
def test_guardrails_de_los_pesos(valores):
    with pytest.raises(ValidationError):
        Pesos(**valores)


def test_el_total_es_la_suma_ponderada_y_dice_con_que_pesos():
    d = evaluar(joven(), vacante(), MatrizTraslados(MATRIZ), CERCANIA)
    assert d.pesos == CERCANIA
    assert d.total == pytest.approx(0.2 * d.habilidades + 0.7 * d.traslado + 0.1 * d.salario, abs=1e-3)


def test_mas_peso_al_traslado_cambia_el_orden():
    m = MatrizTraslados(MATRIZ)
    cerca, lejos = cerca_y_lejos()
    j = joven()
    assert evaluar(j, lejos, m).total > evaluar(j, cerca, m).total                     # por defecto
    assert evaluar(j, cerca, m, CERCANIA).total > evaluar(j, lejos, m, CERCANIA).total


# ---------- orquestador ----------

@pytest.fixture
def orq():
    o = Orquestador(Almacen(), mercado=MercadoFalso(), auditor=AuditorFalso(),
                    notificador=NotificadorFalso(), reloj=lambda: VIERNES)
    o.almacen.guardar_traslados(MATRIZ)
    o.registrar_joven(joven())
    for v in cerca_y_lejos():
        o.publicar_vacante(v)
        o.deslizar("joven", "j1", v.id, True)
        o.deslizar("empresa", "j1", v.id, True)
    return o


def test_cambiar_pesos_exige_motivo_y_queda_trazado(orq):
    with pytest.raises(ErrorDeFlujo):
        orq.cambiar_pesos(CERCANIA, " ")
    orq.cambiar_pesos(CERCANIA, "Priorizar empleos cerca de casa en Panamá Oeste")
    assert orq.pesos() == CERCANIA
    t = orq.almacen.trazas("orientador")[0]
    assert t.accion == "cambiar_pesos" and t.entrada["antes"]["traslado"] == 0.25
    assert t.salida["despues"]["traslado"] == 0.7


def test_las_tarjetas_y_el_matching_usan_los_pesos_nuevos(orq):
    assert [v.id for v, _ in orq.tarjetas_joven("j1")] == []          # ya deslizó ambas
    assert orq.ejecutar_matching().asignaciones[0].vacante_id == "lejos"
    orq.cambiar_pesos(CERCANIA, "Cercanía")
    assert orq.ejecutar_matching().asignaciones[0].vacante_id == "cerca"


def test_cambiar_pesos_retira_las_propuestas_calculadas_con_los_viejos(orq):
    orq.ejecutar_matching()
    orq.cambiar_pesos(CERCANIA, "Cercanía")
    assert [a for a in orq.almacen.listar(Asignacion) if a.vigente and a.aprobada is None] == []


def test_simular_muestra_que_cambia_sin_guardar_nada(orq):
    orq.ejecutar_matching()
    sim = orq.simular_pesos(CERCANIA)
    assert [(c.joven_id, c.vacante_id) for c in sim.entran] == [("j1", "cerca")]
    assert [(c.joven_id, c.vacante_id) for c in sim.salen] == [("j1", "lejos")]
    assert sim.se_mantienen == 0
    assert orq.pesos() == Pesos()                                      # nada cambió
    assert [a.vacante_id for a in orq.almacen.listar(Asignacion)] == ["lejos"]


# ---------- API ----------

def test_pesos_por_http(orq):
    from fastapi.testclient import TestClient

    from api.main import crear_app
    orq.almacen.guardar_credencial("t-ori", "orientador", None)
    orq.almacen.guardar_credencial("t-j1", "joven", "j1")
    c = TestClient(crear_app(orq))
    ori, jov = {"Authorization": "Bearer t-ori"}, {"Authorization": "Bearer t-j1"}
    nuevos = {"habilidades": 0.2, "traslado": 0.7, "salario": 0.1}
    assert c.get("/pesos").json()["habilidades"] == 0.6                               # público
    assert c.put("/pesos", json={"pesos": nuevos, "motivo": "x"}, headers=jov).status_code == 403
    assert c.post("/pesos/simular", json=nuevos, headers=jov).status_code == 403
    malos = {"habilidades": 0.5, "traslado": 0.5, "salario": 0.5}
    assert c.put("/pesos", json={"pesos": malos, "motivo": "x"}, headers=ori).status_code == 422
    assert c.post("/pesos/simular", json=nuevos, headers=ori).json()["entran"][0]["vacante_id"] == "cerca"
    assert c.put("/pesos", json={"pesos": nuevos, "motivo": "Cercanía"}, headers=ori).json() == nuevos
    assert c.get("/pesos").json() == nuevos
