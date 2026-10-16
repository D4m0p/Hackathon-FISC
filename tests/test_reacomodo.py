from datetime import datetime, timezone

import pytest

from contrato.modelos import DatosPersonales, EstadoVacante, TipoCierre, Traslado
from orquestador import Almacen, ErrorDeFlujo, NoEncontrado, Orquestador
from orquestador.agenda import PANAMA
from tests.test_orquestador import AuditorFalso, MercadoFalso, NotificadorFalso, joven, vacante

VIERNES = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def orq():
    o = Orquestador(Almacen(), mercado=MercadoFalso(), auditor=AuditorFalso(),
                    notificador=NotificadorFalso(), reloj=lambda: VIERNES)
    o.almacen.guardar_traslados([Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0)])
    return o


def mutuo(o, j, v):
    o.deslizar("joven", j, v, True)
    o.deslizar("empresa", j, v, True)


def dos_candidatos_un_cupo(o):
    """j1 y j2 quieren v1 (1 cupo). Devuelve (ganador, suplente) tras aprobar al ganador."""
    for j in ("j1", "j2"):
        o.registrar_joven(joven(j), DatosPersonales(joven_id=j, nombre=j.upper(), contacto_telegram=j))
    o.publicar_vacante(vacante("v1"))
    mutuo(o, "j1", "v1")
    mutuo(o, "j2", "v1")
    ganador = o.ejecutar_matching().asignaciones[0].joven_id
    o.orientador_decidir(ganador, "v1", aprobar=True)
    return ganador, ({"j1", "j2"} - {ganador}).pop()


# ---------- liberar un cupo ----------

def test_cancelacion_libera_el_cupo_y_propone_al_suplente(orq):
    ganador, suplente = dos_candidatos_un_cupo(orq)
    liberada, nuevas = orq.liberar(ganador, "v1", TipoCierre.cancelacion_joven, "Consiguió otro empleo")
    assert liberada.vigente is False and liberada.tipo_cierre == TipoCierre.cancelacion_joven
    assert [(a.joven_id, a.vacante_id, a.aprobada) for a in nuevas] == [(suplente, "v1", None)]
    assert "reacomodar" in [t.accion for t in orq.almacen.trazas("matching")]


def test_el_suplente_aprobado_no_excede_los_cupos(orq):
    ganador, suplente = dos_candidatos_un_cupo(orq)
    orq.liberar(ganador, "v1", TipoCierre.inasistencia, "No se presentó")
    orq.orientador_decidir(suplente, "v1", aprobar=True)
    from contrato.modelos import Asignacion
    vivas = [a for a in orq.almacen.listar(Asignacion) if a.vigente and a.aprobada]
    assert [(a.joven_id, a.vacante_id) for a in vivas] == [(suplente, "v1")]


def test_un_par_cerrado_no_se_vuelve_a_proponer(orq):
    ganador, suplente = dos_candidatos_un_cupo(orq)
    orq.liberar(ganador, "v1", TipoCierre.cancelacion_joven, "Ya no le interesa")
    orq.liberar(suplente, "v1", TipoCierre.cancelacion_joven, "Tampoco")
    assert orq.ejecutar_matching().asignaciones == []


def test_sin_suplente_no_hay_propuestas(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    mutuo(orq, "j1", "v1")
    orq.ejecutar_matching()
    orq.orientador_decidir("j1", "v1", aprobar=True)
    _, nuevas = orq.liberar("j1", "v1", TipoCierre.inasistencia, "No llegó")
    assert nuevas == []


def test_liberar_exige_motivo_y_asignacion_vigente(orq):
    ganador, _ = dos_candidatos_un_cupo(orq)
    with pytest.raises(ErrorDeFlujo):
        orq.liberar(ganador, "v1", TipoCierre.inasistencia, " ")
    with pytest.raises(NoEncontrado):
        orq.liberar("nadie", "v1", TipoCierre.inasistencia, "x")
    orq.liberar(ganador, "v1", TipoCierre.inasistencia, "No llegó")
    with pytest.raises(ErrorDeFlujo):
        orq.liberar(ganador, "v1", TipoCierre.inasistencia, "otra vez")


def test_cerrar_vacante_no_se_hace_con_liberar(orq):
    ganador, _ = dos_candidatos_un_cupo(orq)
    with pytest.raises(ErrorDeFlujo):
        orq.liberar(ganador, "v1", TipoCierre.vacante_cerrada, "x")


def test_retiro_de_la_empresa_avisa_al_joven_y_la_inasistencia_no(orq):
    ganador, suplente = dos_candidatos_un_cupo(orq)
    antes = len(orq.notificador.enviados)
    orq.liberar(ganador, "v1", TipoCierre.retiro_empresa, "Cambió el perfil del puesto")
    destino, texto = orq.notificador.enviados[-1]
    assert len(orq.notificador.enviados) == antes + 1
    assert destino == ganador and "canceló el proceso" in texto
    orq.orientador_decidir(suplente, "v1", aprobar=True)
    antes = len(orq.notificador.enviados)
    orq.liberar(suplente, "v1", TipoCierre.inasistencia, "No llegó")
    assert len(orq.notificador.enviados) == antes


def test_una_pendiente_cancelada_ya_no_se_puede_aprobar(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    mutuo(orq, "j1", "v1")
    orq.ejecutar_matching()
    orq.liberar("j1", "v1", TipoCierre.cancelacion_joven, "Se mudó")
    with pytest.raises(ErrorDeFlujo):
        orq.orientador_decidir("j1", "v1", aprobar=True)


# ---------- cerrar una vacante ----------

def test_cerrar_vacante_reubica_a_quien_tenia_entrevista(orq):
    orq.registrar_joven(joven("j1"), DatosPersonales(joven_id="j1", nombre="Ana", contacto_telegram="1"))
    orq.publicar_vacante(vacante("v1"))
    orq.publicar_vacante(vacante("v2"))
    mutuo(orq, "j1", "v1")
    mutuo(orq, "j1", "v2")
    elegida = orq.ejecutar_matching().asignaciones[0].vacante_id
    orq.orientador_decidir("j1", elegida, aprobar=True)
    otra = ({"v1", "v2"} - {elegida}).pop()

    v, afectadas, nuevas = orq.cerrar_vacante(elegida, "La empresa congeló contrataciones")
    assert v.estado == EstadoVacante.cerrada
    assert [a.tipo_cierre for a in afectadas] == [TipoCierre.vacante_cerrada]
    assert [(a.joven_id, a.vacante_id) for a in nuevas] == [("j1", otra)]
    assert "se cerró" in orq.notificador.enviados[-1][1]
    with pytest.raises(ErrorDeFlujo):
        orq.cerrar_vacante(elegida, "otra vez")


def test_vacante_cerrada_no_da_tarjetas(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    orq.cerrar_vacante("v1", "Se llenó por otra vía")
    assert orq.tarjetas_joven("j1") == []


def test_cerrar_exige_motivo(orq):
    orq.publicar_vacante(vacante("v1"))
    with pytest.raises(ErrorDeFlujo):
        orq.cerrar_vacante("v1", "")


# ---------- reprogramar ----------

def test_reprogramar_mueve_al_siguiente_dia_habil_y_avisa(orq):
    ganador, _ = dos_candidatos_un_cupo(orq)            # entrevista: lunes 19, 9:00
    a = orq.reprogramar_entrevista(ganador, "v1", "Tiene examen ese día")
    assert a.entrevista == datetime(2026, 10, 20, 9, 0, tzinfo=PANAMA)
    assert "se movió al 20/10/2026 a las 09:00" in orq.notificador.enviados[-1][1]


def test_solo_se_reprograma_una_aprobada(orq):
    orq.registrar_joven(joven("j1"))
    orq.publicar_vacante(vacante("v1"))
    mutuo(orq, "j1", "v1")
    orq.ejecutar_matching()
    with pytest.raises(ErrorDeFlujo):
        orq.reprogramar_entrevista("j1", "v1", "x")
    orq.orientador_decidir("j1", "v1", aprobar=True)
    with pytest.raises(ErrorDeFlujo):
        orq.reprogramar_entrevista("j1", "v1", "")


# ---------- API ----------

def test_reacomodo_por_http(orq):
    from conftest import cliente_orientador
    c = cliente_orientador(orq)
    ganador, suplente = dos_candidatos_un_cupo(orq)
    r = c.post(f"/asignaciones/{ganador}/v1/liberar", json={"tipo": "inasistencia", "motivo": "No llegó"})
    assert r.status_code == 200 and r.json()["nuevas"][0]["joven_id"] == suplente
    assert [a["joven_id"] for a in c.get("/asignaciones", params={"estado": "cerrada"}).json()] == [ganador]
    assert c.post(f"/asignaciones/{suplente}/v1/liberar",
                  json={"tipo": "vacante_cerrada", "motivo": "x"}).status_code == 422
    assert c.post("/vacantes/v1/cerrar", json={"motivo": "Se llenó"}).json()["vacante"]["estado"] == "cerrada"
