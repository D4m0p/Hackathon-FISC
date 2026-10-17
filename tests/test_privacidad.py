"""La empresa revisa candidatos anónimos: nada de lo que recibe puede identificar al joven."""
from fastapi.testclient import TestClient

from api.main import crear_app
from contrato.modelos import Habilidad, Traslado
from orquestador import Almacen, Orquestador

CV = ("Me llamo María González, cédula 8-888-8888, tel 6000-0000, y atiendo clientes y cobro "
      "en la caja de la tienda de mi tía")
DATOS_PERSONALES = ("María", "González", "8-888-8888", "6000-0000", "femenino")


def sistema():
    o = Orquestador(Almacen())
    a = o.almacen
    a.guardar_traslados([Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0)])
    for cod, n in [("atencion_cliente", "Atención al cliente"), ("manejo_caja", "Manejo de caja")]:
        a.guardar(Habilidad(codigo=cod, nombre=n))
    a.guardar_credencial("te", "empresa", "e1")
    a.guardar_credencial("to", "orientador", None)
    c = TestClient(crear_app(o))
    c.post("/vacantes", headers={"Authorization": "Bearer te"}, json={
        "id": "v1", "empresa_id": "e1", "titulo": "Cajero", "corregimiento": "arraijan",
        "turnos": ["manana"], "salario_mensual": 650, "habilidades_requeridas": [{"codigo": "manejo_caja"}]})
    hab = c.post("/perfil/cv", json={"tipo": "texto", "texto": CV}).json()["habilidades"]
    assert any("María" in (h.get("evidencia") or "") for h in hab)   # el caso de riesgo existe
    token = c.post("/jovenes", json={
        "joven": {"id": "j1", "corregimiento": "la_chorrera", "disponibilidad": ["manana"],
                  "presupuesto_transporte_semanal": 20, "salario_minimo": 0, "habilidades": hab},
        "datos": {"joven_id": "j1", "nombre": "María González", "genero": "femenino"}}).json()["token"]
    return c, token


def test_la_empresa_no_recibe_nada_que_identifique_al_candidato():
    c, token = sistema()
    tarjetas = c.get("/vacantes/v1/tarjetas", headers={"Authorization": "Bearer te"})
    assert tarjetas.status_code == 200 and len(tarjetas.json()) == 1
    for dato in DATOS_PERSONALES:
        assert dato not in tarjetas.text, dato
    hab = tarjetas.json()[0]["joven"]["habilidades"]
    assert {h["codigo"] for h in hab} >= {"manejo_caja"} and all(h["evidencia"] is None for h in hab)

    # tampoco después del match, en sus asignaciones
    c.post("/deslizar", headers={"Authorization": f"Bearer {token}"},
           json={"actor": "joven", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    c.post("/deslizar", headers={"Authorization": "Bearer te"},
           json={"actor": "empresa", "joven_id": "j1", "vacante_id": "v1", "le_interesa": True})
    c.post("/matching", headers={"Authorization": "Bearer to"})
    asignaciones = c.get("/asignaciones", headers={"Authorization": "Bearer te"})
    assert len(asignaciones.json()) == 1
    for dato in DATOS_PERSONALES:
        assert dato not in asignaciones.text, dato


def test_el_joven_si_ve_su_propia_evidencia():
    c, token = sistema()
    perfil = c.get("/jovenes/j1", headers={"Authorization": f"Bearer {token}"}).json()
    assert any(h["evidencia"] for h in perfil["habilidades"])
