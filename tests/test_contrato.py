import pytest
from pydantic import ValidationError

from contrato.modelos import (
    DatosPersonales, HabilidadNivel, Joven, ResultadoAuditoria, Turno, Vacante,
)


def joven(**cambios):
    datos = dict(id="j1", corregimiento="la_chorrera", disponibilidad={Turno.manana},
                 presupuesto_transporte_semanal=15, salario_minimo=600)
    datos.update(cambios)
    return Joven(**datos)


def test_joven_no_tiene_datos_personales():
    campos = set(Joven.model_fields)
    assert not campos & {"nombre", "genero", "edad"}


def test_datos_personales_van_aparte():
    d = DatosPersonales(joven_id="j1", nombre="Ana")
    assert d.genero.value == "no_indica"


def test_joven_sin_disponibilidad_es_invalido():
    with pytest.raises(ValidationError):
        joven(disponibilidad=set())


def test_presupuesto_negativo_es_invalido():
    with pytest.raises(ValidationError):
        joven(presupuesto_transporte_semanal=-1)


def test_nivel_de_habilidad_fuera_de_rango():
    with pytest.raises(ValidationError):
        HabilidadNivel(codigo="atencion_cliente", nivel=4)


def test_vacante_necesita_al_menos_un_cupo():
    with pytest.raises(ValidationError):
        Vacante(id="v1", empresa_id="e1", titulo="Cajero", corregimiento="tocumen",
                turnos={Turno.tarde}, salario_mensual=650, cupos=0)


def test_rechazo_de_auditoria_sin_hallazgos_es_invalido():
    with pytest.raises(ValidationError):
        ResultadoAuditoria(tipo="oferta", objeto_id="v1", aprobado=False)


def test_turnos_llegan_como_texto_desde_json():
    j = Joven.model_validate_json(
        '{"id":"j1","corregimiento":"x","disponibilidad":["tarde","noche"],'
        '"presupuesto_transporte_semanal":10,"salario_minimo":0}')
    assert j.disponibilidad == {Turno.tarde, Turno.noche}


# ---------- guardrails de tamaño y forma ----------

@pytest.mark.parametrize("id_malo", ["a/b", "con espacio", "x?y=1", "", "x" * 65, "'; DROP TABLE entidades; --"])
def test_ids_que_romperian_la_url_o_la_base_se_rechazan(id_malo):
    with pytest.raises(ValidationError):
        joven(id=id_malo)


def test_ids_reales_se_aceptan():
    for bueno in ("j01", "j-1a2b3c4d", "carga_0001", "v.2026"):
        assert joven(id=bueno).id == bueno


def test_textos_y_listas_tienen_tope():
    with pytest.raises(ValidationError):
        DatosPersonales(joven_id="j1", nombre="N" * 121)
    with pytest.raises(ValidationError):
        joven(habilidades=[HabilidadNivel(codigo=f"h{i}", nivel=1) for i in range(51)])
    with pytest.raises(ValidationError):
        Vacante(id="v1", empresa_id="e1", titulo="T", corregimiento="a", turnos={Turno.manana},
                salario_mensual=600, texto_original="x" * 5001)
