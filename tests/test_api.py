import pytest
from conftest import cliente_orientador
from orquestador import Almacen, Orquestador

VACANTE = {"id": "v1", "empresa_id": "e1", "titulo": "Cajero", "corregimiento": "arraijan",
           "turnos": ["manana"], "salario_mensual": 650,
           "habilidades_requeridas": [{"codigo": "caja"}]}
JOVEN = {"id": "j1", "corregimiento": "la_chorrera", "disponibilidad": ["manana", "tarde"],
         "presupuesto_transporte_semanal": 20, "salario_minimo": 500,
         "habilidades": [{"codigo": "caja", "nivel": 1}]}
DATOS = {"joven_id": "j1", "nombre": "Ana Pérez", "genero": "femenino", "edad": 19,
         "contacto_telegram": "123"}


@pytest.fixture
def cliente():
    orq = Orquestador(Almacen())
    c = cliente_orientador(orq)
    c.post("/traslados", json=[{"origen": "la_chorrera", "destino": "arraijan",
                                "minutos": 30, "costo": 1.0}])
    return c


def preparar(c):
    assert c.post("/vacantes", json=VACANTE).status_code == 200
    assert c.post("/jovenes", json={"joven": JOVEN, "datos": DATOS}).status_code == 200


def test_salud_dice_que_agentes_estan_conectados(cliente):
    r = cliente.get("/salud").json()
    assert r["estado"] == "ok" and r["auditor"] == "AuditorProvisional"


def test_flujo_completo_por_http(cliente):
    preparar(cliente)
    tarjetas = cliente.get("/jovenes/j1/tarjetas").json()
    assert [t["vacante"]["id"] for t in tarjetas] == ["v1"]
    assert tarjetas[0]["desglose"]["motivos"]

    r = cliente.post("/deslizar", json={"actor": "joven", "joven_id": "j1",
                                        "vacante_id": "v1", "le_interesa": True})
    assert r.json() == {"interes_mutuo": False}
    r = cliente.post("/deslizar", json={"actor": "empresa", "joven_id": "j1",
                                        "vacante_id": "v1", "le_interesa": True})
    assert r.json() == {"interes_mutuo": True}

    m = cliente.post("/matching").json()
    assert m["asignaciones"][0]["aprobada"] is None
    assert len(cliente.get("/asignaciones", params={"estado": "pendiente"}).json()) == 1

    a = cliente.post("/asignaciones/j1/v1/decision", json={"aprobar": True}).json()
    assert a["aprobada"] is True and a["entrevista"]
    assert "Ana Pérez" in cliente.get("/mensajes").json()[0]["texto"]
    agentes = {t["agente"] for t in cliente.get("/trazas").json()}
    assert {"perfil", "auditor", "matching", "orientador", "orquestador"} <= agentes


def test_la_empresa_no_ve_datos_personales(cliente):
    preparar(cliente)
    cuerpo = cliente.get("/vacantes/v1/tarjetas").text
    for dato in ("Ana", "femenino", "123", "nombre", "genero", "edad"):
        assert dato not in cuerpo


def test_recurso_inexistente_da_404(cliente):
    assert cliente.get("/jovenes/nadie/tarjetas").status_code == 404
    assert cliente.get("/vacantes/nada").status_code == 404
    assert cliente.post("/asignaciones/j1/v1/decision", json={"aprobar": True}).status_code == 404


def test_regla_del_flujo_da_400(cliente):
    preparar(cliente)
    cliente.post("/deslizar", json={"actor": "joven", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    cliente.post("/deslizar", json={"actor": "empresa", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    cliente.post("/matching")
    r = cliente.post("/asignaciones/j1/v1/decision", json={"aprobar": False})
    assert r.status_code == 400 and "motivo" in r.json()["detail"]


def test_datos_invalidos_dan_422(cliente):
    malo = dict(JOVEN, presupuesto_transporte_semanal=-5)
    assert cliente.post("/jovenes", json={"joven": malo}).status_code == 422
    assert cliente.post("/deslizar", json={"actor": "orientador", "joven_id": "j1",
                                           "vacante_id": "v1", "le_interesa": True}).status_code == 422


def test_oferta_demasiado_larga_se_rechaza_antes_del_llm(cliente):
    r = cliente.post("/ofertas", json={"texto": "x" * 5001, "empresa_id": "e1"})
    assert r.status_code == 422


def test_sin_agente_de_mercado_la_oferta_en_texto_da_501(cliente):
    r = cliente.post("/ofertas", json={"texto": "Se busca cajero en Arraiján", "empresa_id": "e1"})
    assert r.status_code == 501


def test_plan_inexistente_da_404(cliente):
    preparar(cliente)
    assert cliente.get("/jovenes/j1/plan").status_code == 404


def test_filtrar_vacantes_por_estado(cliente):
    preparar(cliente)
    assert len(cliente.get("/vacantes", params={"estado": "publicada"}).json()) == 1
    assert cliente.get("/vacantes", params={"estado": "bloqueada"}).json() == []


def test_cors_permite_el_frontend_local(cliente):
    r = cliente.options("/salud", headers={"Origin": "http://localhost:5173",
                                           "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
