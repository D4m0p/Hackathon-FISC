"""Autonomía: el sistema reacciona solo (vacante publicada, joven nuevo, interés mutuo) y el
orientador sigue aprobando."""
from datetime import datetime, timezone

from contrato.modelos import Asignacion, Curso, HabilidadNivel, PlanFormacion, Traslado, Turno
from orquestador import Almacen, Orquestador
from tests.test_orquestador import AuditorFalso, MercadoFalso, NotificadorFalso, joven, vacante

VIERNES = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)


def sistema(automatico=True):
    o = Orquestador(Almacen(), mercado=MercadoFalso(), auditor=AuditorFalso(),
                    notificador=NotificadorFalso(), reloj=lambda: VIERNES, automatico=automatico)
    o.almacen.guardar_traslados([Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0)])
    return o


def autos(o):
    return [t for t in o.almacen.trazas("matching") if t.accion == "auto_matching"]


def pendientes(o):
    return [(a.joven_id, a.vacante_id) for a in o.almacen.listar(Asignacion) if a.vigente and a.aprobada is None]


def test_interes_mutuo_genera_la_propuesta_sin_tocar_el_boton():
    o = sistema()
    o.registrar_joven(joven("j1"))
    o.publicar_vacante(vacante("v1"))
    o.deslizar("joven", "j1", "v1", True)
    assert pendientes(o) == []
    o.deslizar("empresa", "j1", "v1", True)
    assert pendientes(o) == [("j1", "v1")]                 # sin llamar a ejecutar_matching
    t = autos(o)[0]
    assert t.entrada == {"disparador": "interes_mutuo", "objeto_id": "j1|v1", "joven_id": "j1"}
    assert t.salida == {"nuevas": ["j1|v1"]} and "j1→v1" in t.motivo
    assert o.orientador_decidir("j1", "v1", aprobar=True).aprobada is True   # el humano decide


def test_vacante_publicada_dispara_y_lo_dice_aunque_no_haya_propuestas():
    o = sistema()
    o.publicar_vacante(vacante("v1"))
    t = autos(o)[0]
    assert t.entrada["disparador"] == "vacante_publicada" and "ninguna" in t.motivo


def test_vacante_bloqueada_no_dispara_hasta_que_el_orientador_la_publica():
    o = sistema()
    o.publicar_vacante(vacante("v1", texto_original="buena presencia"))
    assert autos(o) == []
    o.orientador_publicar_bloqueada("v1", "Era un requisito de uniforme")
    assert autos(o)[0].entrada["disparador"] == "vacante_publicada"


def test_joven_nuevo_sin_opciones_recibe_su_ruta_de_formacion_al_registrarse():
    o = sistema()
    o.almacen.guardar(Curso(id="c1", centro="INADEH", nombre="Caja", corregimiento="la_chorrera",
                            turnos={Turno.tarde}, sesiones_por_semana=2, semanas=4, cupos_disponibles=5,
                            habilidades_otorgadas=[HabilidadNivel(codigo="caja", nivel=1)]))
    o.publicar_vacante(vacante("v1"))
    o.registrar_joven(joven("j1", habilidades=()))          # le falta "caja"
    plan = o.almacen.obtener(PlanFormacion, "j1")
    assert plan is not None and plan.cursos == ["c1"]
    t = autos(o)[0]
    assert t.entrada["disparador"] == "joven_nuevo" and "ruta de formación" in t.motivo


def test_joven_nuevo_con_vacantes_no_recibe_plan():
    o = sistema()
    o.publicar_vacante(vacante("v1"))
    o.registrar_joven(joven("j1"))
    assert o.almacen.obtener(PlanFormacion, "j1") is None
    assert "interés mutuo" in autos(o)[0].motivo


def test_actualizar_un_perfil_no_cuenta_como_joven_nuevo():
    o = sistema()
    o.registrar_joven(joven("j1"))
    n = len(autos(o))
    o.registrar_joven(joven("j1", presupuesto_transporte_semanal=30))
    assert len(autos(o)) == n


def test_apagado_no_dispara_nada():
    o = sistema(automatico=False)
    o.registrar_joven(joven("j1"))
    o.publicar_vacante(vacante("v1"))
    o.deslizar("joven", "j1", "v1", True)
    o.deslizar("empresa", "j1", "v1", True)
    assert autos(o) == [] and pendientes(o) == []


def test_la_api_lo_enciende_y_la_semilla_no():
    import os
    from orquestador.arranque import orquestador_desde_entorno
    os.environ["RUTA_BASE_DATOS"] = ":memory:"
    assert orquestador_desde_entorno().automatico is True
    assert orquestador_desde_entorno(automatico=False).automatico is False


def test_interes_mutuo_no_cambia_los_planes_de_nadie():
    """Optimización: con un interés mutuo no se rearman las rutas; deben quedar idénticas a
    las que daría un matching completo."""
    o = sistema()
    o.almacen.guardar(Curso(id="c1", centro="INADEH", nombre="Caja", corregimiento="la_chorrera",
                            turnos={Turno.tarde}, sesiones_por_semana=2, semanas=4, cupos_disponibles=5,
                            habilidades_otorgadas=[HabilidadNivel(codigo="caja", nivel=1)]))
    o.publicar_vacante(vacante("v1", cupos=2))
    o.registrar_joven(joven("sin", habilidades=()))
    o.registrar_joven(joven("j1"))
    o.deslizar("joven", "j1", "v1", True)
    o.deslizar("empresa", "j1", "v1", True)
    planes = {p.joven_id: p for p in o.almacen.listar(PlanFormacion)}
    o.ejecutar_matching()                                  # completo, con planes
    assert {p.joven_id: p for p in o.almacen.listar(PlanFormacion)} == planes
