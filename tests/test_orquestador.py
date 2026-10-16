from datetime import datetime, timezone

import pytest

from contrato.modelos import (
    Curso, DatosPersonales, EstadoVacante, HabilidadNivel, Hallazgo, Joven, RequisitoHabilidad,
    ResultadoAuditoria, Traslado, Turno, Vacante,
)
from orquestador import Almacen, ErrorDeFlujo, Orquestador
from orquestador.agenda import PANAMA, proxima_entrevista

VIERNES = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)


class AuditorFalso:
    def __init__(self):
        self.matchings_auditados = 0

    def auditar_oferta(self, v):
        if "buena presencia" in (v.texto_original or "").lower():
            return ResultadoAuditoria(tipo="oferta", objeto_id=v.id, aprobado=False, hallazgos=[
                Hallazgo(regla="buena_presencia", fragmento="buena presencia",
                         detalle="Requisito de apariencia física")])
        return ResultadoAuditoria(tipo="oferta", objeto_id=v.id, aprobado=True)

    def auditar_matching(self, resultado, jovenes, datos, vacantes, matriz):
        self.matchings_auditados += 1
        return [ResultadoAuditoria(tipo="contrafactual", objeto_id="lote", aprobado=True)]


class MercadoFalso:
    def normalizar_oferta(self, texto, empresa_id):
        return Vacante(id="v_txt", empresa_id=empresa_id, titulo=texto.split(".")[0],
                       corregimiento="arraijan", turnos={Turno.manana}, salario_mensual=650,
                       habilidades_requeridas=[RequisitoHabilidad(codigo="caja")],
                       texto_original=texto)


class NotificadorFalso:
    def __init__(self):
        self.enviados = []

    def enviar(self, destino, texto):
        self.enviados.append((destino, texto))
        return True


def vacante(id="v1", **cambios):
    datos = dict(id=id, empresa_id="e1", titulo="Cajero", corregimiento="arraijan",
                 turnos={Turno.manana}, salario_mensual=650,
                 habilidades_requeridas=[RequisitoHabilidad(codigo="caja")])
    datos.update(cambios)
    return Vacante(**datos)


def joven(id="j1", habilidades=("caja",), **cambios):
    datos = dict(id=id, corregimiento="la_chorrera", disponibilidad={Turno.manana, Turno.tarde},
                 presupuesto_transporte_semanal=20, salario_minimo=500,
                 habilidades=[HabilidadNivel(codigo=c, nivel=1) for c in habilidades])
    datos.update(cambios)
    return Joven(**datos)


@pytest.fixture
def sistema():
    almacen = Almacen()
    almacen.guardar_traslados([
        Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0),
        Traslado(origen="la_chorrera", destino="tocumen", minutos=110, costo=2.5),
    ])
    auditor, notificador = AuditorFalso(), NotificadorFalso()
    orq = Orquestador(almacen, mercado=MercadoFalso(), auditor=auditor,
                      notificador=notificador, reloj=lambda: VIERNES)
    return orq, auditor, notificador


def acciones(orq, agente=None):
    return [t.accion for t in orq.almacen.trazas(agente)]


# ---------- ofertas ----------

def test_oferta_limpia_se_publica_y_queda_trazada(sistema):
    orq, _, _ = sistema
    v, r = orq.publicar_vacante(vacante())
    assert v.estado == EstadoVacante.publicada and r.aprobado
    assert "auditar_oferta" in acciones(orq, "auditor")


def test_oferta_discriminatoria_queda_bloqueada_y_sin_candidatos(sistema):
    orq, _, _ = sistema
    orq.registrar_joven(joven())
    v, r = orq.publicar_vacante(vacante(texto_original="Cajera de buena presencia"))
    assert v.estado == EstadoVacante.bloqueada and not r.aprobado
    assert orq.tarjetas_vacante("v1") == [] and orq.tarjetas_joven("j1") == []
    with pytest.raises(ErrorDeFlujo):
        orq.deslizar("joven", "j1", "v1", True)


def test_orientador_publica_bloqueada_solo_con_motivo(sistema):
    orq, _, _ = sistema
    orq.publicar_vacante(vacante(texto_original="buena presencia"))
    with pytest.raises(ErrorDeFlujo):
        orq.orientador_publicar_bloqueada("v1", "  ")
    v = orq.orientador_publicar_bloqueada("v1", "Se refería a uniforme limpio; aclarado con la empresa")
    assert v.estado == EstadoVacante.publicada
    assert "publicar_bloqueada" in acciones(orq, "orientador")


def test_publicar_oferta_pasa_por_mercado_y_auditor(sistema):
    orq, _, _ = sistema
    v, _ = orq.publicar_oferta("Cajero en Arraiján. Turno mañana.", "e9")
    assert v.id == "v_txt" and v.empresa_id == "e9"
    assert acciones(orq)[:2] == ["auditar_oferta", "normalizar_oferta"]   # más reciente primero


def test_auditor_provisional_deja_constancia():
    orq = Orquestador(Almacen())
    orq.publicar_vacante(vacante())
    assert "provisional" in orq.almacen.trazas("auditor")[0].motivo.lower()


def test_mercado_provisional_avisa_que_falta():
    with pytest.raises(NotImplementedError):
        Orquestador(Almacen()).publicar_oferta("texto", "e1")


# ---------- jóvenes y tarjetas ----------

def test_datos_personales_deben_ser_del_mismo_joven(sistema):
    orq, _, _ = sistema
    with pytest.raises(ErrorDeFlujo):
        orq.registrar_joven(joven(), DatosPersonales(joven_id="otro", nombre="Ana"))


def test_tarjeta_deslizada_ya_no_aparece(sistema):
    orq, _, _ = sistema
    orq.registrar_joven(joven())
    orq.publicar_vacante(vacante("v1"))
    orq.publicar_vacante(vacante("v2"))
    orq.deslizar("joven", "j1", "v1", False)
    assert [v.id for v, _ in orq.tarjetas_joven("j1")] == ["v2"]


def test_no_se_puede_deslizar_un_par_infactible(sistema):
    orq, _, _ = sistema
    orq.registrar_joven(joven())
    orq.publicar_vacante(vacante(corregimiento="tocumen"))
    with pytest.raises(ErrorDeFlujo):
        orq.deslizar("joven", "j1", "v1", True)


def test_actor_invalido(sistema):
    orq, _, _ = sistema
    with pytest.raises(ErrorDeFlujo):
        orq.deslizar("orientador", "j1", "v1", True)


def test_interes_mutuo_se_detecta_y_se_traza(sistema):
    orq, _, _ = sistema
    orq.registrar_joven(joven())
    orq.publicar_vacante(vacante())
    assert orq.deslizar("joven", "j1", "v1", True) is False
    assert orq.deslizar("empresa", "j1", "v1", True) is True
    assert "interes_mutuo" in acciones(orq, "orquestador")


# ---------- flujo completo ----------

def preparar_match(orq):
    orq.registrar_joven(joven(), DatosPersonales(joven_id="j1", nombre="Ana", contacto_telegram="123"))
    orq.publicar_vacante(vacante())
    orq.deslizar("joven", "j1", "v1", True)
    orq.deslizar("empresa", "j1", "v1", True)


def test_flujo_completo_hasta_el_mensaje(sistema):
    orq, auditor, notificador = sistema
    preparar_match(orq)
    r = orq.ejecutar_matching()
    assert [(a.joven_id, a.vacante_id, a.aprobada) for a in r.asignaciones] == [("j1", "v1", None)]
    assert auditor.matchings_auditados == 1

    a = orq.orientador_decidir("j1", "v1", aprobar=True)
    assert a.aprobada is True
    assert a.entrevista == datetime(2026, 10, 19, 9, 0, tzinfo=PANAMA)   # lunes, turno mañana
    destino, texto = notificador.enviados[0]
    assert destino == "123" and "Hola, Ana." in texto and "19/10/2026 a las 09:00" in texto
    assert orq.almacen.mensajes()[0]["enviado"] is True
    hechas = acciones(orq)
    for accion in ("asignar", "resumen", "auditar_matching", "aprobar", "agendar_y_notificar"):
        assert accion in hechas


def test_sin_interes_mutuo_no_hay_asignacion(sistema):
    orq, _, _ = sistema
    orq.registrar_joven(joven())
    orq.publicar_vacante(vacante())
    orq.deslizar("joven", "j1", "v1", True)
    assert orq.ejecutar_matching().asignaciones == []


def test_quien_queda_sin_asignar_recibe_plan_de_formacion(sistema):
    orq, _, _ = sistema
    orq.registrar_joven(joven(habilidades=()))
    orq.publicar_vacante(vacante())
    orq.almacen.guardar(Curso(id="c1", centro="INADEH", nombre="Caja", corregimiento="la_chorrera",
                              turnos={Turno.tarde}, sesiones_por_semana=2, semanas=4,
                              cupos_disponibles=5,
                              habilidades_otorgadas=[HabilidadNivel(codigo="caja", nivel=1)]))
    orq.ejecutar_matching()
    plan = orq.plan_de("j1")
    assert plan.cursos == ["c1"] and plan.vacantes_objetivo == ["v1"]
    assert "planificar" in acciones(orq, "formacion")


def test_quien_tiene_vacantes_factibles_no_recibe_plan(sistema):
    orq, _, _ = sistema
    orq.registrar_joven(joven())          # tiene "caja": v1 le es factible
    orq.publicar_vacante(vacante())
    orq.ejecutar_matching()               # sin interés mutuo: queda sin asignar
    assert orq.plan_de("j1") is None


def test_rechazo_exige_motivo_y_no_se_vuelve_a_proponer(sistema):
    orq, _, _ = sistema
    preparar_match(orq)
    orq.ejecutar_matching()
    with pytest.raises(ErrorDeFlujo):
        orq.orientador_decidir("j1", "v1", aprobar=False)
    orq.orientador_decidir("j1", "v1", aprobar=False, motivo="El joven ya consiguió empleo")
    assert orq.ejecutar_matching().asignaciones == []


def test_una_decision_no_se_toma_dos_veces(sistema):
    orq, _, _ = sistema
    preparar_match(orq)
    orq.ejecutar_matching()
    orq.orientador_decidir("j1", "v1", aprobar=True)
    with pytest.raises(ErrorDeFlujo):
        orq.orientador_decidir("j1", "v1", aprobar=True)


def test_aprobada_ocupa_su_cupo_en_la_siguiente_corrida(sistema):
    orq, _, _ = sistema
    preparar_match(orq)
    orq.registrar_joven(joven("j2"))
    orq.deslizar("joven", "j2", "v1", True)
    orq.deslizar("empresa", "j2", "v1", True)
    primera = orq.ejecutar_matching()             # 1 cupo: entra uno solo
    elegido = primera.asignaciones[0].joven_id
    orq.orientador_decidir(elegido, "v1", aprobar=True)
    segunda = orq.ejecutar_matching()
    assert segunda.asignaciones == []             # el cupo ya está tomado


def test_decidir_sin_asignacion_pendiente(sistema):
    orq, _, _ = sistema
    with pytest.raises(ErrorDeFlujo):
        orq.orientador_decidir("j1", "v1", aprobar=True)


# ---------- agenda ----------

def test_entrevista_de_fin_de_semana_cae_sabado():
    j = joven(disponibilidad={Turno.fin_de_semana})
    v = vacante(turnos={Turno.fin_de_semana})
    assert proxima_entrevista(j, v, VIERNES) == datetime(2026, 10, 17, 10, 0, tzinfo=PANAMA)


def test_espacio_ocupado_corre_media_hora():
    ocupado = {datetime(2026, 10, 19, 9, 0, tzinfo=PANAMA)}
    assert proxima_entrevista(joven(), vacante(), VIERNES, ocupado).minute == 30


# ---------- almacén ----------

def test_el_almacen_persiste_en_disco(tmp_path):
    ruta = str(tmp_path / "datos.db")
    Almacen(ruta).guardar(joven())
    assert Almacen(ruta).obtener(Joven, "j1").id == "j1"


def test_trazas_filtradas_por_agente_y_mas_recientes_primero(sistema):
    orq, _, _ = sistema
    orq.publicar_vacante(vacante("v1"))
    orq.publicar_vacante(vacante("v2"))
    trazas = orq.almacen.trazas("auditor")
    assert [t.entrada["vacante_id"] for t in trazas] == ["v2", "v1"]


# ---------- concurrencia ----------

def test_dos_aprobaciones_simultaneas_solo_una_gana():
    import threading
    import time

    def reloj_lento():
        time.sleep(0.05)          # ensancha la ventana entre leer "pendiente" y guardar
        return VIERNES

    notificador = NotificadorFalso()
    orq = Orquestador(Almacen(), mercado=MercadoFalso(), auditor=AuditorFalso(),
                      notificador=notificador, reloj=reloj_lento)
    orq.almacen.guardar_traslados([Traslado(origen="la_chorrera", destino="arraijan",
                                            minutos=30, costo=1.0)])
    preparar_match(orq)
    orq.ejecutar_matching()

    resultados = []

    def decidir():
        try:
            orq.orientador_decidir("j1", "v1", aprobar=True)
            resultados.append("ok")
        except ErrorDeFlujo:
            resultados.append("rechazada")

    hilos = [threading.Thread(target=decidir) for _ in range(5)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert resultados.count("ok") == 1
    assert len(notificador.enviados) == 1
