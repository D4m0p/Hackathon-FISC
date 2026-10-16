"""Errores que encontraron las pruebas con secuencias aleatorias, fijados uno por uno."""
from datetime import datetime, timezone

import pytest

from contrato.modelos import Asignacion, EstadoVacante, Traslado, Turno
from orquestador import Almacen, ErrorDeFlujo, Orquestador
from tests.test_orquestador import AuditorFalso, MercadoFalso, NotificadorFalso, joven, vacante

VIERNES = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def orq():
    o = Orquestador(Almacen(), mercado=MercadoFalso(), auditor=AuditorFalso(),
                    notificador=NotificadorFalso(), reloj=lambda: VIERNES)
    o.almacen.guardar_traslados([Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0)])
    return o


def aprobar(o, j, v):
    o.deslizar("joven", j, v, True)
    o.deslizar("empresa", j, v, True)
    o.ejecutar_matching()
    o.orientador_decidir(j, v, aprobar=True)


def pendientes(o):
    return [(a.joven_id, a.vacante_id) for a in o.almacen.listar(Asignacion) if a.vigente and a.aprobada is None]


def test_no_se_bajan_cupos_por_debajo_de_los_aprobados(orq):
    for j in ("j1", "j2"):
        orq.registrar_joven(joven(j))
    orq.publicar_vacante(vacante("v1", cupos=2))
    aprobar(orq, "j1", "v1")
    aprobar(orq, "j2", "v1")
    with pytest.raises(ErrorDeFlujo, match="no puede bajar a 1 cupo"):
        orq.publicar_vacante(vacante("v1", cupos=1))
    assert orq._vacante("v1").cupos == 2                      # se mantiene la versión anterior


def test_edicion_discriminatoria_con_aprobados_se_rechaza(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    aprobar(orq, "j1", "v1")
    with pytest.raises(ErrorDeFlujo, match="discriminatorios"):
        orq.publicar_vacante(vacante("v1", texto_original="buena presencia"))
    assert orq._vacante("v1").estado == EstadoVacante.publicada


def test_edicion_que_deja_mal_a_un_aprobado_se_rechaza(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    aprobar(orq, "j1", "v1")
    with pytest.raises(ErrorDeFlujo, match="j1"):
        orq.publicar_vacante(vacante("v1", turnos={Turno.noche}))


def test_editar_la_vacante_retira_las_propuestas_pendientes(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    orq.deslizar("joven", "j1", "v1", True)
    orq.deslizar("empresa", "j1", "v1", True)
    orq.ejecutar_matching()
    orq.publicar_vacante(vacante("v1", salario_mensual=700))
    assert pendientes(orq) == []
    assert "retirar_propuesta" in [t.accion for t in orq.almacen.trazas("orquestador")]


def test_cambiar_a_no_despues_del_matching_retira_la_propuesta(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    orq.deslizar("joven", "j1", "v1", True)
    orq.deslizar("empresa", "j1", "v1", True)
    orq.ejecutar_matching()
    orq.deslizar("empresa", "j1", "v1", False)
    assert pendientes(orq) == []


def test_cambiar_el_perfil_retira_propuestas_y_avisa_si_choca_con_una_aprobada(orq):
    orq.registrar_joven(joven("j1"))
    orq.registrar_joven(joven("j2"))
    orq.publicar_vacante(vacante("v1", cupos=2))
    aprobar(orq, "j1", "v1")
    orq.deslizar("joven", "j2", "v1", True)
    orq.deslizar("empresa", "j2", "v1", True)
    orq.ejecutar_matching()
    orq.registrar_joven(joven("j2", presupuesto_transporte_semanal=0))    # pendiente ya no es factible
    assert pendientes(orq) == []
    orq.registrar_joven(joven("j1", disponibilidad={Turno.tarde}))         # choca con su entrevista
    assert "advertencia" in [t.accion for t in orq.almacen.trazas("orquestador")]


def test_reprogramar_sin_turno_en_comun_da_error_claro_y_no_se_cae(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    aprobar(orq, "j1", "v1")
    orq.registrar_joven(joven("j1", disponibilidad={Turno.tarde}))
    with pytest.raises(ErrorDeFlujo, match="disponibilidad ya no coincide"):
        orq.reprogramar_entrevista("j1", "v1", "Cambió de horario")


def test_no_se_cambia_el_deslizamiento_de_una_entrevista_aprobada(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    aprobar(orq, "j1", "v1")
    with pytest.raises(ErrorDeFlujo, match="cancélela"):
        orq.deslizar("joven", "j1", "v1", False)
