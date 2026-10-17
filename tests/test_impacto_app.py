from conftest import cliente_orientador
from orquestador import Almacen, Orquestador


def test_impacto_esta_registrado_en_la_app_real():
    c = cliente_orientador(Orquestador(Almacen()))
    r = c.get("/impacto")
    assert r.status_code == 200 and r.json()["pares"] == 0
    c.headers.pop("Authorization")
    assert c.get("/impacto").status_code == 401
