"""Foto del joven: la ven él y el orientador; la empresa SOLO con interés mutuo o entrevista aprobada."""
import base64

import pytest
from fastapi.testclient import TestClient

from api.main import crear_app
from orquestador import Almacen, Orquestador

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JOVEN = {"id": "j1", "corregimiento": "la_chorrera", "disponibilidad": ["manana"],
         "presupuesto_transporte_semanal": 20, "salario_minimo": 0, "habilidades": [{"codigo": "caja", "nivel": 1}]}
VACANTE = {"id": "v1", "empresa_id": "e1", "titulo": "Cajero", "corregimiento": "arraijan",
           "turnos": ["manana"], "salario_mensual": 650, "habilidades_requeridas": [{"codigo": "caja"}]}


def h(t):
    return {"Authorization": f"Bearer {t}"}


def b64(datos):
    return base64.b64encode(datos).decode()


@pytest.fixture
def c():
    orq = Orquestador(Almacen())
    a = orq.almacen
    for t, rol, suj in [("to", "orientador", None), ("te1", "empresa", "e1"), ("te2", "empresa", "e2")]:
        a.guardar_credencial(t, rol, suj)
    cli = TestClient(crear_app(orq))
    cli.post("/traslados", headers=h("to"), json=[{"origen": "la_chorrera", "destino": "arraijan", "minutos": 30, "costo": 1.0}])
    tj = cli.post("/jovenes", json={"joven": JOVEN, "datos": {"joven_id": "j1", "nombre": "Ana"}}).json()["token"]
    cli.post("/jovenes", json={"joven": dict(JOVEN, id="j2")})
    a.guardar_credencial("tj2", "joven", "j2")
    cli.post("/vacantes", headers=h("te1"), json=VACANTE)
    cli.tj = tj
    return cli


def subir(c, token, datos=PNG, tipo="image/png", joven="j1"):
    return c.put(f"/jovenes/{joven}/foto", headers=h(token), json={"tipo_mime": tipo, "contenido_base64": b64(datos)})


def aprobar(c):
    c.post("/deslizar", headers=h(c.tj), json={"actor": "joven", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    c.post("/deslizar", headers=h("te1"), json={"actor": "empresa", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    c.post("/matching", headers=h("to"))


def test_el_joven_sube_y_ve_su_foto(c):
    assert subir(c, c.tj).status_code == 204
    r = c.get("/jovenes/j1/foto", headers=h(c.tj))
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
    assert "no-store" in r.headers["cache-control"]
    assert c.get("/jovenes/j1/foto", headers=h("to")).status_code == 200


def test_la_empresa_ve_la_foto_solo_cuando_los_dos_dijeron_que_si(c):
    subir(c, c.tj)
    assert c.get("/jovenes/j1/foto", headers=h("te1")).status_code == 404     # ni siquiera hay interés
    c.post("/deslizar", headers=h(c.tj), json={"actor": "joven", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    assert c.get("/jovenes/j1/foto", headers=h("te1")).status_code == 404     # solo le interesa al joven
    c.post("/deslizar", headers=h("te1"), json={"actor": "empresa", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    r = c.get("/jovenes/j1/foto", headers=h("te1"))
    assert r.status_code == 200 and r.content == PNG                         # la empresa la aceptó: interés mutuo
    assert c.get("/jovenes/j1/foto", headers=h("te2")).status_code == 404    # otra empresa, nunca


def test_la_empresa_que_no_acepta_no_ve_la_foto(c):
    subir(c, c.tj)
    c.post("/deslizar", headers=h(c.tj), json={"actor": "joven", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    c.post("/deslizar", headers=h("te1"), json={"actor": "empresa", "joven_id": "j1", "vacante_id": "v1", "le_interesa": False})
    assert c.get("/jovenes/j1/foto", headers=h("te1")).status_code == 404


def test_si_el_orientador_rechaza_el_match_la_empresa_deja_de_verla(c):
    subir(c, c.tj)
    aprobar(c)
    assert c.get("/jovenes/j1/foto", headers=h("te1")).status_code == 200
    c.post("/asignaciones/j1/v1/decision", headers=h("to"), json={"aprobar": False, "motivo": "No cumple el horario real"})
    assert c.get("/jovenes/j1/foto", headers=h("te1")).status_code == 404


def test_si_la_entrevista_se_cancela_la_empresa_deja_de_verla(c):
    subir(c, c.tj)
    aprobar(c)
    c.post("/asignaciones/j1/v1/decision", headers=h("to"), json={"aprobar": True})
    c.post("/asignaciones/j1/v1/liberar", headers=h(c.tj), json={"tipo": "cancelacion_joven", "motivo": "Otro empleo"})
    assert c.get("/jovenes/j1/foto", headers=h("te1")).status_code == 404


def test_permisos_para_subir_y_borrar(c):
    assert subir(c, "tj2").status_code == 403                                 # otro joven
    assert subir(c, "te1").status_code == 403                                 # una empresa
    assert c.put("/jovenes/j1/foto", json={"tipo_mime": "image/png", "contenido_base64": b64(PNG)}).status_code == 401
    subir(c, c.tj)
    assert c.delete("/jovenes/j1/foto", headers=h("tj2")).status_code == 403
    assert c.delete("/jovenes/j1/foto", headers=h(c.tj)).status_code == 204
    assert c.get("/jovenes/j1/foto", headers=h(c.tj)).status_code == 404


def test_solo_imagenes_reales_y_de_tamano_razonable(c):
    assert subir(c, c.tj, datos=b"<svg onload=alert(1)>", tipo="image/png").status_code == 400
    assert subir(c, c.tj, datos=PNG, tipo="image/jpeg").status_code == 400     # dice JPG pero es PNG
    assert c.put("/jovenes/j1/foto", headers=h(c.tj),
                 json={"tipo_mime": "image/gif", "contenido_base64": b64(PNG)}).status_code == 422
    assert c.put("/jovenes/j1/foto", headers=h(c.tj),
                 json={"tipo_mime": "image/png", "contenido_base64": "no es base64!!"}).status_code == 400
    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024)
    assert subir(c, c.tj, datos=grande).status_code == 413


def test_la_foto_no_aparece_en_las_tarjetas_de_la_empresa(c):
    subir(c, c.tj)
    cuerpo = c.get("/vacantes/v1/tarjetas", headers=h("te1")).text
    assert "foto" not in cuerpo.lower() and b64(PNG)[:12] not in cuerpo
