"""Un joven nuevo sin CV entra al sistema de punta a punta: entrevista (agente Perfil)
→ registro → token → tarjetas. Sin LLM: el Perfil usa palabras clave."""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import crear_app
from orquestador import Almacen, Orquestador

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from semilla_demo import DATOS, cargar  # noqa: E402


def sistema():
    orq = Orquestador(Almacen())
    cargar(orq, json.loads(DATOS.read_text(encoding="utf-8")))
    return TestClient(crear_app(orq)), orq


def test_joven_sin_cv_llega_a_sus_tarjetas():
    c, orq = sistema()
    assert c.get("/salud").json()["perfil"] == "palabras_clave"
    preguntas = c.get("/perfil/preguntas").json()                       # sin token
    assert any(p["id"] == "negocio" for p in preguntas)

    r = c.post("/perfil/entrevista", json={"respuestas": [
        {"pregunta_id": "negocio", "texto": "Atiendo la tienda de mi tía los sábados y cobro en la caja."}]})
    assert r.status_code == 200
    codigos = {h["codigo"] for h in r.json()["habilidades"]}
    assert "manejo_caja" in codigos
    assert all(h["evidencia"] for h in r.json()["habilidades"])        # cada una con su evidencia

    registro = c.post("/jovenes", json={
        "joven": {"id": "nuevo", "corregimiento": "la_chorrera", "disponibilidad": ["manana", "tarde"],
                  "presupuesto_transporte_semanal": 15, "salario_minimo": 550,
                  "habilidades": r.json()["habilidades"]},
        "datos": {"joven_id": "nuevo", "nombre": "Joven Nuevo"}}).json()
    token = registro["token"]
    tarjetas = c.get("/jovenes/nuevo/tarjetas", headers={"Authorization": f"Bearer {token}"}).json()
    assert "v01" in [t["vacante"]["id"] for t in tarjetas]               # cajero/a en Arraiján

    acciones = [t.accion for t in orq.almacen.trazas("perfil")]
    assert "entrevista" in acciones and "registrar_joven" in acciones


def test_la_traza_del_perfil_no_guarda_el_texto_del_cv():
    c, orq = sistema()
    secreto = "Mi cédula es 8-888-8888 y atiendo clientes en la tienda"
    assert c.post("/perfil/cv", json={"tipo": "texto", "texto": secreto}).status_code == 200
    volcado = json.dumps([t.model_dump(mode="json") for t in orq.almacen.trazas("perfil")])
    assert "8-888-8888" not in volcado
