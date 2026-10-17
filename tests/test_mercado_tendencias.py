"""Pruebas de las tendencias de mercado por zona."""
from agentes.mercado import tendencias_por_zona, vacantes_por_zona
from contrato.modelos import Habilidad, RequisitoHabilidad, Turno, Vacante

TAXONOMIA = {h.codigo: h for h in [
    Habilidad(codigo=c, nombre=n) for c, n in [
        ("manejo_caja", "Manejo de caja"), ("atencion_cliente", "Atención al cliente"),
        ("ventas", "Ventas")]]}


def vacante(id, corregimiento, codigos):
    return Vacante(id=id, empresa_id="e1", titulo="Puesto", corregimiento=corregimiento,
                   turnos={Turno.manana}, salario_mensual=600,
                   habilidades_requeridas=[RequisitoHabilidad(codigo=c) for c in codigos])


def test_cuenta_habilidades_por_zona():
    vs = [vacante("v1", "arraijan", ["manejo_caja", "atencion_cliente"]),
          vacante("v2", "arraijan", ["manejo_caja"]),
          vacante("v3", "la_chorrera", ["ventas"])]
    t = tendencias_por_zona(vs, TAXONOMIA)
    assert t["arraijan"] == [("manejo_caja", 2), ("atencion_cliente", 1)]
    assert t["la_chorrera"] == [("ventas", 1)]


def test_respeta_el_limite_top_y_el_orden():
    vs = [vacante("v1", "arraijan", ["manejo_caja", "atencion_cliente", "ventas"]),
          vacante("v2", "arraijan", ["manejo_caja", "atencion_cliente"]),
          vacante("v3", "arraijan", ["manejo_caja"])]
    assert tendencias_por_zona(vs, TAXONOMIA, top=2) == {
        "arraijan": [("manejo_caja", 3), ("atencion_cliente", 2)]}


def test_ignora_codigos_fuera_de_la_taxonomia():
    vs = [vacante("v1", "arraijan", ["manejo_caja", "piloto_avion"])]
    assert tendencias_por_zona(vs, TAXONOMIA) == {"arraijan": [("manejo_caja", 1)]}


def test_sin_vacantes_devuelve_vacio():
    assert tendencias_por_zona([], TAXONOMIA) == {}
    assert vacantes_por_zona([]) == {}


def test_vacantes_por_zona_cuenta_todas():
    vs = [vacante("v1", "arraijan", []), vacante("v2", "arraijan", []),
          vacante("v3", "tocumen", [])]
    assert vacantes_por_zona(vs) == {"arraijan": 2, "tocumen": 1}