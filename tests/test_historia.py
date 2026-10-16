from datetime import datetime, timezone

import pytest

from contrato.modelos import Curso, DatosPersonales, HabilidadNivel, TipoCierre, Traslado, Turno
from orquestador import Almacen, Orquestador
from tests.test_orquestador import AuditorFalso, MercadoFalso, NotificadorFalso, joven, vacante

VIERNES = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def orq():
    o = Orquestador(Almacen(), mercado=MercadoFalso(), auditor=AuditorFalso(),
                    notificador=NotificadorFalso(), reloj=lambda: VIERNES)
    o.almacen.guardar_traslados([
        Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0),
        Traslado(origen="la_chorrera", destino="bella_vista", minutos=70, costo=1.6)])
    return o


def mutuo(o, j, v):
    o.deslizar("joven", j, v, True)
    o.deslizar("empresa", j, v, True)


def acciones(h):
    return [e.accion for e in h.eventos]


def test_recien_registrado_esta_buscando(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    h = orq.historia("j1")
    assert h.estado == "Buscando: tiene 1 vacante(s) por revisar"
    assert acciones(h) == ["registrar_joven"]


def test_estado_menciona_las_que_casi_califica(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1", corregimiento="bella_vista"))   # factible: 70 min, B/.16 por semana
    orq.publicar_vacante(vacante("v2", salario_mensual=450))           # paga menos que su mínimo (500)
    assert "1 donde le falta una sola cosa" in orq.historia("j1").estado


def test_de_punta_a_punta_en_orden(orq):
    orq.registrar_joven(joven("j1"), DatosPersonales(joven_id="j1", nombre="Ana"))
    orq.publicar_vacante(vacante("v1"))
    mutuo(orq, "j1", "v1")
    orq.ejecutar_matching()
    assert orq.historia("j1").estado.startswith("Propuesto para «Cajero», pendiente")
    orq.orientador_decidir("j1", "v1", aprobar=True)
    h = orq.historia("j1")
    assert h.estado == "Entrevista agendada para «Cajero» el 19/10/2026 a las 09:00"
    assert acciones(h) == ["registrar_joven", "interes_mutuo", "asignar", "aprobar", "agendar_y_notificar"]
    assert [e.agente.value for e in h.eventos] == ["perfil", "orquestador", "matching", "orientador", "orquestador"]
    assert [(d["actor"], d["vacante_id"]) for d in h.deslizamientos] == [("joven", "v1"), ("empresa", "v1")]


def test_el_suplente_ve_en_su_historia_que_lo_propuso_el_reacomodo(orq):
    for j in ("j1", "j2"):
        orq.registrar_joven(joven(j))
    orq.publicar_vacante(vacante("v1"))
    mutuo(orq, "j1", "v1")
    mutuo(orq, "j2", "v1")
    ganador = orq.ejecutar_matching().asignaciones[0].joven_id
    suplente = ({"j1", "j2"} - {ganador}).pop()
    orq.orientador_decidir(ganador, "v1", aprobar=True)
    orq.liberar(ganador, "v1", TipoCierre.inasistencia, "No llegó")
    assert "reacomodar" in acciones(orq.historia(suplente))
    assert acciones(orq.historia(ganador))[-1] == "liberar_cupo"


def test_no_mezcla_jovenes_con_ids_parecidos(orq):
    orq.registrar_joven(joven("j1"))
    orq.registrar_joven(joven("j10"))
    orq.publicar_vacante(vacante("v1", cupos=2))
    mutuo(orq, "j10", "v1")
    orq.ejecutar_matching()
    assert acciones(orq.historia("j1")) == ["registrar_joven"]
    assert "asignar" in acciones(orq.historia("j10"))


def test_ruta_de_formacion_y_plan_trazado_una_sola_vez(orq):
    orq.registrar_joven(joven("j1", habilidades=()))
    orq.publicar_vacante(vacante("v1"))
    orq.almacen.guardar(Curso(id="c1", centro="INADEH", nombre="Caja", corregimiento="la_chorrera",
                              turnos={Turno.tarde}, sesiones_por_semana=2, semanas=4, cupos_disponibles=5,
                              habilidades_otorgadas=[HabilidadNivel(codigo="caja", nivel=1)]))
    for _ in range(3):
        orq.ejecutar_matching()
    h = orq.historia("j1")
    assert h.estado.startswith("Sin vacante factible por ahora: en ruta de formación")
    assert acciones(h).count("planificar") == 1 and h.plan.cursos == ["c1"]


def test_historia_por_http_con_permisos(orq):
    from fastapi.testclient import TestClient

    from api.main import crear_app
    orq.registrar_joven(joven("j1"))
    orq.registrar_joven(joven("j2"))
    orq.almacen.guardar_credencial("t-j1", "joven", "j1")
    orq.almacen.guardar_credencial("t-ori", "orientador", None)
    c = TestClient(crear_app(orq))
    assert c.get("/jovenes/j1/historia", headers={"Authorization": "Bearer t-j1"}).status_code == 200
    assert c.get("/jovenes/j2/historia", headers={"Authorization": "Bearer t-j1"}).status_code == 403
    assert c.get("/jovenes/j2/historia", headers={"Authorization": "Bearer t-ori"}).json()["joven"]["id"] == "j2"
    assert c.get("/jovenes/nadie/historia", headers={"Authorization": "Bearer t-ori"}).status_code == 404
