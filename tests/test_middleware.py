"""Límite para anónimos, errores inesperados y registro de peticiones."""
import logging

from fastapi.testclient import TestClient

from api.main import crear_app
from orquestador import Almacen, Orquestador

JOVEN = {"id": "j1", "corregimiento": "la_chorrera", "disponibilidad": ["manana"],
         "presupuesto_transporte_semanal": 20, "salario_minimo": 500,
         "habilidades": [{"codigo": "caja", "nivel": 1}]}


def h(token):
    return {"Authorization": f"Bearer {token}"}


def app_con(limite=3):
    orq = Orquestador(Almacen())
    orq.almacen.guardar_credencial("t-ori", "orientador", None)
    return crear_app(orq, limite_anonimo_por_minuto=limite), orq


def test_anonimo_recibe_429_al_pasar_el_tope():
    app, _ = app_con(3)
    c = TestClient(app)
    for _ in range(3):
        assert c.post("/perfil/entrevista", json={"respuestas": []}).status_code != 429
    r = c.post("/perfil/entrevista", json={"respuestas": []})
    assert r.status_code == 429
    assert r.json() == {"detail": "Demasiadas solicitudes seguidas. Espere un momento e intente de nuevo."}
    assert int(r.headers["Retry-After"]) >= 1


def test_el_tope_cuenta_las_tres_rutas_juntas():
    app, _ = app_con(2)
    c = TestClient(app)
    c.post("/perfil/cv", json={})
    c.post("/jovenes", json={})
    assert c.post("/perfil/entrevista", json={"respuestas": []}).status_code == 429


def test_con_token_valido_no_se_limita():
    app, orq = app_con(2)
    c = TestClient(app)
    token = c.post("/jovenes", json={"joven": JOVEN}).json()["token"]
    for _ in range(6):   # el propio joven actualiza su perfil
        assert c.post("/jovenes", headers=h(token), json={"joven": JOVEN}).status_code == 200
    for i in range(6):   # el orientador
        assert c.post("/jovenes", headers=h("t-ori"), json={"joven": dict(JOVEN, id=f"x{i}")}).status_code != 429


def test_token_invalido_si_se_limita():
    app, _ = app_con(2)
    c = TestClient(app)
    codigos = [c.post("/perfil/entrevista", headers=h("falso"), json={"respuestas": []}).status_code
               for _ in range(3)]
    assert codigos[-1] == 429


def test_rutas_no_limitadas_no_dan_429():
    app, _ = app_con(1)
    c = TestClient(app)
    assert all(c.get("/salud").status_code == 200 for _ in range(10))


def test_error_inesperado_da_500_generico_con_id(caplog):
    app, _ = app_con()

    @app.get("/boom")
    def boom():
        raise RuntimeError("secreto")

    c = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.INFO, logger="empleo.api"):
        r = c.get("/boom")
    assert r.status_code == 500
    assert "secreto" not in r.text
    cuerpo = r.json()
    assert cuerpo["id_error"] and cuerpo["id_error"] == r.headers["X-Id-Peticion"]
    errores = [x for x in caplog.records if x.levelno == logging.ERROR]
    assert errores and cuerpo["id_error"] in errores[0].getMessage()
    assert "Traceback" in errores[0].getMessage() and "RuntimeError: secreto" in errores[0].getMessage()


def test_id_de_peticion_generado_y_respetado():
    app, _ = app_con()
    c = TestClient(app)
    assert c.get("/salud").headers["X-Id-Peticion"]
    assert c.get("/salud", headers={"X-Id-Peticion": "abc123"}).headers["X-Id-Peticion"] == "abc123"
    invalido = c.get("/salud", headers={"X-Id-Peticion": "no valido!"}).headers["X-Id-Peticion"]
    assert invalido != "no valido!" and invalido.isalnum()


def test_el_registro_no_incluye_token_ni_query(caplog):
    app, _ = app_con()
    c = TestClient(app)
    with caplog.at_level(logging.INFO, logger="empleo.api"):
        c.get("/vacantes?estado=publicada&secreto=zzz", headers=h("t-ori"))
    lineas = [x.getMessage() for x in caplog.records if x.name == "empleo.api"]
    assert any("GET /vacantes 200" in x for x in lineas)
    for linea in lineas:
        assert "t-ori" not in linea and "secreto" not in linea and "estado=" not in linea and "?" not in linea
