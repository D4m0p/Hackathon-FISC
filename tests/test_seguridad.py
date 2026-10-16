"""Roles y permisos: cada actor solo puede tocar lo suyo; las decisiones son del orientador."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.main import crear_app
from orquestador import Almacen, Orquestador

JOVEN = {"id": "j1", "corregimiento": "la_chorrera", "disponibilidad": ["manana"],
         "presupuesto_transporte_semanal": 20, "salario_minimo": 500,
         "habilidades": [{"codigo": "caja", "nivel": 1}]}
VACANTE = {"id": "v1", "empresa_id": "e1", "titulo": "Cajero", "corregimiento": "arraijan",
           "turnos": ["manana"], "salario_mensual": 650, "habilidades_requeridas": [{"codigo": "caja"}]}


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def s():
    """Sistema con orientador, dos empresas y dos jóvenes, cada uno con su token."""
    orq = Orquestador(Almacen())
    a = orq.almacen
    a.guardar_credencial("t-ori", "orientador", None)
    a.guardar_credencial("t-e1", "empresa", "e1")
    a.guardar_credencial("t-e2", "empresa", "e2")
    c = TestClient(crear_app(orq))
    c.post("/traslados", headers=h("t-ori"),
           json=[{"origen": "la_chorrera", "destino": "arraijan", "minutos": 30, "costo": 1.0}])
    tokens = {}
    for jid in ("j1", "j2"):
        r = c.post("/jovenes", json={"joven": dict(JOVEN, id=jid)})
        tokens[jid] = r.json()["token"]
    c.post("/vacantes", headers=h("t-e1"), json=VACANTE)
    return c, orq, tokens


# ---------- autenticación ----------

def test_rutas_protegidas_sin_token_dan_401(s):
    c, _, _ = s
    for metodo, ruta in [("GET", "/jovenes/j1/tarjetas"), ("POST", "/matching"), ("GET", "/trazas"),
                         ("GET", "/asignaciones"), ("GET", "/yo")]:
        assert c.request(metodo, ruta).status_code == 401, ruta


def test_token_invalido_da_401(s):
    c, _, _ = s
    assert c.get("/yo", headers=h("inventado")).status_code == 401


def test_rutas_publicas_funcionan_sin_token(s):
    c, _, _ = s
    for ruta in ("/salud", "/habilidades", "/cursos", "/traslados", "/vacantes", "/vacantes/v1"):
        assert c.get(ruta).status_code == 200, ruta


def test_yo_dice_quien_es(s):
    c, _, t = s
    assert c.get("/yo", headers=h(t["j1"])).json() == {"rol": "joven", "sujeto": "j1"}


def test_los_tokens_se_guardan_solo_como_hash(s, tmp_path):
    ruta = str(tmp_path / "x.db")
    a = Almacen(ruta)
    a.guardar_credencial("secreto-muy-largo", "orientador", None)
    volcado = "\n".join(sqlite3.connect(ruta).iterdump())
    assert "secreto-muy-largo" not in volcado
    assert a.credencial("secreto-muy-largo") == ("orientador", None)


# ---------- jóvenes ----------

def test_registro_nuevo_devuelve_un_token_que_funciona(s):
    c, _, t = s
    assert len(t["j1"]) >= 40
    assert c.get("/jovenes/j1/tarjetas", headers=h(t["j1"])).status_code == 200


def test_nadie_puede_sobrescribir_el_perfil_de_otro(s):
    c, _, t = s
    malo = {"joven": dict(JOVEN, id="j1", salario_minimo=9999)}
    assert c.post("/jovenes", json=malo).status_code == 403                    # sin token
    assert c.post("/jovenes", json=malo, headers=h(t["j2"])).status_code == 403
    r = c.post("/jovenes", json=malo, headers=h(t["j1"]))                     # el dueño sí
    assert r.status_code == 200 and r.json()["token"] is None


def test_un_joven_no_ve_lo_de_otro(s):
    c, _, t = s
    for ruta in ("/jovenes/j2", "/jovenes/j2/tarjetas", "/jovenes/j2/casi-califica", "/jovenes/j2/plan"):
        assert c.get(ruta, headers=h(t["j1"])).status_code == 403, ruta


def test_un_joven_no_desliza_por_otro_ni_como_empresa(s):
    c, _, t = s
    por_otro = {"actor": "joven", "joven_id": "j2", "vacante_id": "v1", "le_interesa": True}
    como_empresa = {"actor": "empresa", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True}
    assert c.post("/deslizar", json=por_otro, headers=h(t["j1"])).status_code == 403
    assert c.post("/deslizar", json=como_empresa, headers=h(t["j1"])).status_code == 403


def test_un_joven_no_puede_hacer_lo_del_orientador(s):
    c, _, t = s
    for metodo, ruta, cuerpo in [("POST", "/matching", None), ("GET", "/trazas", None),
                                 ("GET", "/mensajes", None), ("GET", "/jovenes", None),
                                 ("POST", "/asignaciones/j1/v1/decision", {"aprobar": True}),
                                 ("POST", "/cursos", []), ("POST", "/credenciales", {"rol": "orientador"})]:
        assert c.request(metodo, ruta, json=cuerpo, headers=h(t["j1"])).status_code == 403, ruta


# ---------- empresas ----------

def test_una_empresa_no_publica_a_nombre_de_otra(s):
    c, _, _ = s
    assert c.post("/vacantes", headers=h("t-e2"), json=dict(VACANTE, id="v9")).status_code == 403
    assert c.post("/ofertas", headers=h("t-e2"),
                  json={"texto": "Se busca cajero urgente", "empresa_id": "e1"}).status_code == 403


def test_una_empresa_no_puede_pisar_la_vacante_de_otra(s):
    c, _, _ = s
    pisada = dict(VACANTE, empresa_id="e2", titulo="Cambiada")
    assert c.post("/vacantes", headers=h("t-e2"), json=pisada).status_code == 403
    assert c.get("/vacantes/v1").json()["titulo"] == "Cajero"


def test_una_empresa_solo_ve_candidatos_y_desliza_en_sus_vacantes(s):
    c, _, _ = s
    assert c.get("/vacantes/v1/tarjetas", headers=h("t-e2")).status_code == 403
    d = {"actor": "empresa", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True}
    assert c.post("/deslizar", json=d, headers=h("t-e2")).status_code == 403
    assert c.post("/deslizar", json=d, headers=h("t-e1")).status_code == 200


def test_una_empresa_no_cierra_la_vacante_de_otra(s):
    c, _, _ = s
    assert c.post("/vacantes/v1/cerrar", json={"motivo": "x"}, headers=h("t-e2")).status_code == 403


def test_vacante_bloqueada_no_se_revela_al_publico(s):
    c, orq, _ = s
    from contrato.modelos import EstadoVacante, Vacante
    orq.almacen.guardar(Vacante(**dict(VACANTE, id="vb", estado=EstadoVacante.bloqueada)))
    assert c.get("/vacantes/vb").status_code == 404
    assert "vb" not in [v["id"] for v in c.get("/vacantes").json()]
    assert c.get("/vacantes/vb", headers=h("t-e1")).status_code == 200          # su dueña sí


# ---------- flujo completo, cada uno con su token ----------

def test_flujo_con_roles_reales(s):
    c, _, t = s
    assert c.post("/deslizar", headers=h(t["j1"]), json={
        "actor": "joven", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True}).status_code == 200
    r = c.post("/deslizar", headers=h("t-e1"), json={
        "actor": "empresa", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    assert r.json()["interes_mutuo"] is True
    assert c.post("/matching", headers=h("t-ori")).json()["asignaciones"][0]["joven_id"] == "j1"
    assert c.post("/asignaciones/j1/v1/decision", headers=h("t-ori"), json={"aprobar": True}).status_code == 200

    # cada uno ve solo sus asignaciones
    assert len(c.get("/asignaciones", headers=h(t["j1"])).json()) == 1
    assert c.get("/asignaciones", headers=h(t["j2"])).json() == []
    assert len(c.get("/asignaciones", headers=h("t-e1")).json()) == 1
    assert c.get("/asignaciones", headers=h("t-e2")).json() == []

    # reacomodo: la inasistencia es del orientador; cancelar, del propio joven
    inasistencia = {"tipo": "inasistencia", "motivo": "No llegó"}
    assert c.post("/asignaciones/j1/v1/liberar", json=inasistencia, headers=h("t-e1")).status_code == 403
    cancelar = {"tipo": "cancelacion_joven", "motivo": "Consiguió otro"}
    assert c.post("/asignaciones/j1/v1/liberar", json=cancelar, headers=h(t["j2"])).status_code == 403
    assert c.post("/asignaciones/j1/v1/liberar", json=cancelar, headers=h(t["j1"])).status_code == 200


def test_el_orientador_emite_credenciales_de_empresa(s):
    c, _, _ = s
    r = c.post("/credenciales", headers=h("t-ori"), json={"rol": "empresa", "sujeto": "e7"})
    assert c.get("/yo", headers=h(r.json()["token"])).json() == {"rol": "empresa", "sujeto": "e7"}
    assert c.post("/credenciales", headers=h("t-ori"), json={"rol": "empresa"}).status_code == 422
