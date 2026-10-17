"""Centros de formación como tercer lado: ven quién necesita cada curso y reservan cupos."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentes.auditor import Auditor
from api.main import crear_app
from contrato.modelos import Curso, HabilidadNivel, Turno
from orquestador import Almacen, Orquestador

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from semilla_demo import DATOS, cargar, credenciales_demo  # noqa: E402

DEMO = json.loads(DATOS.read_text(encoding="utf-8"))


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sistema():
    orq = Orquestador(Almacen(), auditor=Auditor())
    cargar(orq, DEMO, con_matching=True)
    credenciales_demo(orq, DEMO)
    orq.almacen.guardar(Curso(id="c_otro", centro="OTRO", nombre="Curso ajeno", corregimiento="arraijan",
                              turnos={Turno.manana}, sesiones_por_semana=1, semanas=2, cupos_disponibles=3,
                              habilidades_otorgadas=[HabilidadNivel(codigo="ventas", nivel=1)]))
    return orq, TestClient(crear_app(orq))


def curso(demanda, nombre):
    return next(d for d in demanda if d["curso"]["nombre"] == nombre)


def test_el_token_de_demo_es_un_centro(sistema):
    _, c = sistema
    assert c.get("/yo", headers=h("demo-inadeh")).json() == {"rol": "centro", "sujeto": "INADEH"}


def test_demanda_ordenada_y_sin_datos_personales(sistema):
    orq, c = sistema
    from contrato.modelos import Joven
    r = c.get("/centros/INADEH/demanda", headers=h("demo-inadeh"))
    assert r.status_code == 200
    for dato in ("María", "González", "femenino", "contacto"):
        assert dato not in r.text
    marketing = curso(r.json(), "Marketing digital y redes sociales")
    assert marketing["curso"]["cupos_disponibles"] == 1 and len(marketing["interesados"]) > 1   # escasez
    primero = marketing["interesados"][0]
    assert primero["joven_id"] == "j07" and primero["en_plan"] is True and primero["cabe_en_horario"]
    assert primero["vacantes_que_abre"][0]["titulo"] == "Community manager junior"
    # quienes pueden asistir van antes que quienes no
    for d in r.json():
        puede = [i["cabe_en_horario"] and i["minutos"] is not None
                 and i["minutos"] <= orq.almacen.obtener(Joven, i["joven_id"]).max_minutos_traslado
                 for i in d["interesados"]]
        assert puede == sorted(puede, reverse=True)
    alimentos = curso(r.json(), "Manipulación de alimentos")
    choca = [i for i in alimentos["interesados"] if not i["cabe_en_horario"]]
    assert choca and "horario" in choca[0]["motivo"]


def test_reservar_descuenta_traza_avisa_y_sale_de_la_lista(sistema):
    orq, c = sistema
    marketing = curso(c.get("/centros/INADEH/demanda", headers=h("demo-inadeh")).json(),
                      "Marketing digital y redes sociales")
    cid = marketing["curso"]["id"]
    mensajes_antes = len(orq.almacen.mensajes())
    r = c.post(f"/cursos/{cid}/reservas", headers=h("demo-inadeh"), json={"joven_id": "j07", "motivo": "Le abre 1 vacante"})
    assert r.status_code == 200
    assert r.json()["curso"]["cupos_disponibles"] == 0 and r.json()["reserva"]["joven_id"] == "j07"
    t = orq.almacen.trazas("formacion")[0]
    assert t.accion == "reservar_cupo" and "INADEH" in t.motivo and "j07" in t.motivo
    assert len(orq.almacen.mensajes()) == mensajes_antes + 1
    assert "cupo reservado" in orq.almacen.mensajes()[-1]["texto"]
    despues = curso(c.get("/centros/INADEH/demanda", headers=h("demo-inadeh")).json(),
                    "Marketing digital y redes sociales")
    assert "j07" not in [i["joven_id"] for i in despues["interesados"]]
    assert [x["joven_id"] for x in despues["reservas"]] == ["j07"]
    assert c.get("/jovenes/j07/historia", headers=h("demo-j07")).json()["reservas"][0]["curso_id"] == cid
    # duplicada y sin cupos: 400
    assert c.post(f"/cursos/{cid}/reservas", headers=h("demo-inadeh"), json={"joven_id": "j07"}).status_code == 400
    otro = c.post(f"/cursos/{cid}/reservas", headers=h("demo-inadeh"), json={"joven_id": "j09"})
    assert otro.status_code == 400 and "cupos" in otro.json()["detail"]


def test_permisos_de_los_centros(sistema):
    _, c = sistema
    assert c.get("/centros/INADEH/demanda").status_code == 401
    assert c.get("/centros/OTRO/demanda", headers=h("demo-inadeh")).status_code == 403
    assert c.get("/centros/INADEH/demanda", headers=h("demo-j01")).status_code == 403
    assert c.get("/centros/INADEH/demanda", headers=h("demo-orientador")).status_code == 200
    assert c.post("/cursos/c_otro/reservas", headers=h("demo-inadeh"), json={"joven_id": "j01"}).status_code == 403
    assert c.post("/cursos/c_otro/reservas", headers=h("demo-orientador"), json={"joven_id": "j01"}).status_code == 200
    assert c.post("/cursos/nada/reservas", headers=h("demo-inadeh"), json={"joven_id": "j01"}).status_code == 404
    assert c.post("/cursos/c01/reservas", headers=h("demo-inadeh"), json={"joven_id": "nadie"}).status_code == 404
    assert c.post("/cursos/c01/reservas", headers=h("demo-inadeh"), json={"joven_id": "a/b"}).status_code == 422
    # un centro no puede deslizar ni decidir
    assert c.post("/deslizar", headers=h("demo-inadeh"), json={
        "actor": "joven", "joven_id": "j01", "vacante_id": "v01", "le_interesa": True}).status_code == 403
    assert c.post("/matching", headers=h("demo-inadeh")).status_code == 403


def test_base_vieja_sin_rol_centro_se_migra_sin_perder_credenciales(tmp_path):
    ruta = str(tmp_path / "vieja.db")
    con = sqlite3.connect(ruta)
    con.execute("""CREATE TABLE credenciales (token_hash TEXT PRIMARY KEY,
                   rol TEXT NOT NULL CHECK (rol IN ('joven', 'empresa', 'orientador')), sujeto TEXT)""")
    con.commit()
    con.close()
    a = Almacen(ruta)
    a.guardar_credencial("viejo", "orientador", None)
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO credenciales VALUES ('x', 'joven', 'j1')")
    con.commit()
    con.close()
    a = Almacen(ruta)
    a.guardar_credencial("t-centro", "centro", "INADEH")
    assert a.credencial("t-centro") == ("centro", "INADEH")
    assert a.credencial("viejo") == ("orientador", None)
