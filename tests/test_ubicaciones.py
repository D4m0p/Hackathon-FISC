"""Ubicaciones: estimación por distancia con OpenStreetMap, lugares desconocidos y reinicio de la demo."""
import pytest
from fastapi.testclient import TestClient

from agentes.matching import MatrizTraslados
from agentes.matching.traslados import TARIFA_ESTIMADA, coordenadas_osm, distancia_km
from api.main import crear_app
from contrato.modelos import Traslado
from orquestador import Almacen, Orquestador

COORD = {"a": (9.00, -79.50), "b": (9.00, -79.40), "c": (9.10, -79.50), "d": (9.05, -79.45),
         "e": (8.95, -79.55), "f": (9.02, -79.60), "san_miguelito": (9.03, -79.49)}
TABLA = [Traslado(origen=o, destino=d, minutos=m, costo=0.35) for o, d, m in
         [("a", "c", 40), ("a", "d", 30), ("c", "d", 30), ("a", "e", 35), ("e", "f", 30), ("c", "e", 70)]]


def test_estima_por_distancia_si_falta_en_la_tabla_y_lo_marca():
    m = MatrizTraslados(TABLA, COORD)
    assert m.viaje("a", "c").minutos == 40 and not m.es_estimado("a", "c")      # la tabla manda
    v = m.viaje("a", "b")
    assert v is not None and m.es_estimado("a", "b") and m.es_estimado("b", "a")
    assert v.costo == TARIFA_ESTIMADA
    assert v.minutos == round(distancia_km(COORD["a"], COORD["b"]) * m.minutos_por_km)


def test_el_ritmo_es_conservador_percentil_75():
    m = MatrizTraslados(TABLA, COORD)
    ritmos = sorted(t.minutos / distancia_km(COORD[t.origen], COORD[t.destino]) for t in TABLA)
    assert m.minutos_por_km == ritmos[int(0.75 * (len(ritmos) - 1))]


def test_sin_coordenadas_o_zona_ambigua_no_se_inventa_nada():
    assert MatrizTraslados(TABLA).viaje("a", "b") is None                       # sin coordenadas
    m = MatrizTraslados(TABLA, COORD)
    assert m.viaje("a", "lugar_sin_punto") is None                              # sin punto OSM
    assert m.viaje("a", "san_miguelito") is None                                # distrito, no corregimiento
    assert MatrizTraslados(TABLA[:2], COORD).viaje("a", "b") is None            # pocos viajes de referencia


def test_las_coordenadas_vienen_de_openstreetmap():
    c = coordenadas_osm()
    assert len(c) >= 20 and "bella_vista" in c
    assert all(8.5 < lat < 9.5 and -80.2 < lon < -79.0 for lat, lon in c.values())


# ---------- API ----------

def h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture
def c():
    orq = Orquestador(Almacen())
    orq.almacen.guardar_credencial("to", "orientador", None)
    orq.almacen.guardar_credencial("te1", "empresa", "e1")
    cli = TestClient(crear_app(orq))
    cli.post("/traslados", headers=h("to"), json=[{"origen": "la_chorrera", "destino": "arraijan", "minutos": 30, "costo": 1.0}])
    return cli


VACANTE = {"id": "v1", "empresa_id": "e1", "titulo": "Cajero", "corregimiento": "arraijan",
           "turnos": ["manana"], "salario_mensual": 650, "habilidades_requeridas": []}


def test_ubicacion_desconocida_da_400_con_sugerencias(c):
    r = c.post("/vacantes", headers=h("te1"), json=dict(VACANTE, corregimiento="arraijan_centro"))
    assert r.status_code == 400 and "Arraijan" in r.json()["detail"] and "más cercano" in r.json()["detail"]
    assert c.post("/vacantes", headers=h("te1"), json=VACANTE).status_code == 200          # conocida
    assert c.post("/vacantes", headers=h("te1"), json=dict(VACANTE, id="v2", corregimiento="bella_vista")).status_code == 200  # con punto OSM
    curso = {"id": "k1", "nombre": "Caja", "centro": "INADEH", "corregimiento": "marte", "turnos": ["manana"],
             "sesiones_por_semana": 2, "semanas": 4, "cupos_disponibles": 5,
             "habilidades_otorgadas": [{"codigo": "caja", "nivel": 1}]}
    assert c.post("/cursos", headers=h("to"), json=[curso]).status_code == 400
    joven = {"id": "j1", "corregimiento": "marte", "disponibilidad": ["manana"],
             "presupuesto_transporte_semanal": 10, "salario_minimo": 0, "habilidades": []}
    assert c.post("/jovenes", json={"joven": joven}).status_code == 400


def test_reiniciar_demo_solo_orientador_y_vuelve_a_la_semilla(c):
    assert c.post("/demo/reiniciar", headers=h("te1")).status_code == 403
    c.post("/vacantes", headers=h("te1"), json=VACANTE)
    r = c.post("/demo/reiniciar", headers=h("to"))
    assert r.status_code == 200 and r.json()["jovenes"] >= 10
    ids = {v["id"] for v in c.get("/vacantes", headers=h("demo-orientador")).json()}
    assert "v1" not in ids and len(ids) >= 10                                    # la vacante de prueba ya no está
    assert c.get("/yo", headers=h("demo-j11")).json()["sujeto"] == "j11"          # tokens de demo de nuevo


def test_reiniciar_demo_se_puede_desactivar(c, monkeypatch):
    monkeypatch.setenv("PERMITIR_REINICIAR_DEMO", "0")
    assert c.post("/demo/reiniciar", headers=h("to")).status_code == 403
