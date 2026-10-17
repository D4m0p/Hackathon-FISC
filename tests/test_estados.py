"""Secuencias aleatorias de operaciones sobre el orquestador (máquina de estados de Hypothesis).

Hypothesis inventa recorridos completos: registrar, publicar, deslizar, matching, aprobar,
rechazar, cancelar, inasistencia, retiro, cerrar vacante, reprogramar... y después de CADA
paso se verifican las reglas del negocio. Si alguna se rompe, reduce el recorrido al mínimo
que lo reproduce.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from agentes.matching import motivos_infactible, ranking_para_joven
from contrato.modelos import (
    Asignacion, DatosPersonales, EstadoVacante, HabilidadNivel, Hallazgo, Joven, PlanFormacion,
    RequisitoHabilidad, ResultadoAuditoria, TipoCierre, Traslado, Turno, Vacante,
)
from orquestador import Almacen, ErrorDeFlujo, Orquestador

# Pocos ids a propósito: así las operaciones chocan entre sí (misma vacante, mismo joven).
JOVENES = [f"j{i}" for i in range(3)]
VACANTES = [f"v{i}" for i in range(2)]
LUGARES = ["a", "b"]
HABS = ["caja", "ventas"]


class Auditor:
    def auditar_oferta(self, v):
        if "presencia" in (v.texto_original or ""):
            return ResultadoAuditoria(tipo="oferta", objeto_id=v.id, aprobado=False,
                                      hallazgos=[Hallazgo(regla="presencia", detalle="Apariencia")])
        return ResultadoAuditoria(tipo="oferta", objeto_id=v.id, aprobado=True)

    def auditar_matching(self, *a):
        return []


class Notificador:
    def __init__(self):
        self.enviados = 0

    def enviar(self, destino, texto):
        self.enviados += 1
        return True


class Recorridos(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.notificador = Notificador()
        self.orq = Orquestador(Almacen(), auditor=Auditor(), notificador=self.notificador,
                               reloj=lambda: datetime(2026, 10, 16, 15, tzinfo=timezone.utc))
        self.orq.almacen.guardar_traslados([Traslado(origen="a", destino="b", minutos=40, costo=1.0)])

    # ---------- utilidades ----------
    def asignaciones(self) -> list[Asignacion]:
        return self.orq.almacen.listar(Asignacion)

    def intentar(self, f, *args):
        try:
            f(*args)
        except ErrorDeFlujo:
            pass   # rechazos válidos del flujo (par infactible, ya decidida, etc.)

    # ---------- punto de partida: todos registrados y publicados ----------
    @initialize(cupos=st.lists(st.integers(1, 2), min_size=len(VACANTES), max_size=len(VACANTES)))
    def arrancar(self, cupos):
        for id_ in JOVENES:
            self.orq.registrar_joven(Joven(id=id_, corregimiento="a", disponibilidad={Turno.manana, Turno.tarde},
                                           presupuesto_transporte_semanal=20, salario_minimo=0,
                                           habilidades=[HabilidadNivel(codigo="caja", nivel=1)]),
                                     DatosPersonales(joven_id=id_, nombre=id_))
        for id_, n in zip(VACANTES, cupos):
            self.orq.publicar_vacante(Vacante(id=id_, empresa_id="e", titulo=id_, corregimiento="a",
                                              turnos={Turno.manana}, salario_mensual=600, cupos=n,
                                              texto_original="ok"))

    # ---------- reglas (operaciones) ----------
    @rule(id_=st.sampled_from(JOVENES), lugar=st.sampled_from(LUGARES),
          turnos=st.sets(st.sampled_from([Turno.manana, Turno.tarde]), min_size=1),
          habs=st.lists(st.sampled_from(HABS), unique=True), presupuesto=st.sampled_from([0, 10, 20]))
    def registrar(self, id_, lugar, turnos, habs, presupuesto):
        j = Joven(id=id_, corregimiento=lugar, disponibilidad=turnos,
                  presupuesto_transporte_semanal=presupuesto, salario_minimo=0,
                  habilidades=[HabilidadNivel(codigo=h, nivel=1) for h in habs])
        self.orq.registrar_joven(j, DatosPersonales(joven_id=id_, nombre=id_))

    @rule(id_=st.sampled_from(VACANTES), lugar=st.sampled_from(LUGARES), cupos=st.integers(1, 2),
          req=st.lists(st.sampled_from(HABS), unique=True, max_size=1), discriminatoria=st.booleans(),
          turno=st.sampled_from([Turno.manana, Turno.tarde]))
    def publicar(self, id_, lugar, cupos, req, discriminatoria, turno):
        v = Vacante(id=id_, empresa_id="e", titulo=id_, corregimiento=lugar, turnos={turno},
                    salario_mensual=600, cupos=cupos,
                    habilidades_requeridas=[RequisitoHabilidad(codigo=c) for c in req],
                    texto_original="buena presencia" if discriminatoria else "ok")
        self.intentar(self.orq.publicar_vacante, v)

    @rule(actor=st.sampled_from(["joven", "empresa"]), j=st.sampled_from(JOVENES),
          v=st.sampled_from(VACANTES), si=st.booleans())
    def deslizar(self, actor, j, v, si):
        self.intentar(self.orq.deslizar, actor, j, v, si)

    @rule(j=st.sampled_from(JOVENES), v=st.sampled_from(VACANTES))
    def interes_mutuo(self, j, v):
        self.intentar(self.orq.deslizar, "joven", j, v, True)
        self.intentar(self.orq.deslizar, "empresa", j, v, True)

    @rule()
    def matching(self):
        self.orq.ejecutar_matching()

    @rule(datos=st.data(), aprobar=st.booleans())
    def decidir(self, datos, aprobar):
        pendientes = [a for a in self.asignaciones() if a.vigente and a.aprobada is None]
        if pendientes:
            a = datos.draw(st.sampled_from(pendientes))
            self.orq.orientador_decidir(a.joven_id, a.vacante_id, aprobar, "" if aprobar else "No encaja")

    @rule(datos=st.data(), tipo=st.sampled_from([TipoCierre.cancelacion_joven, TipoCierre.inasistencia,
                                                 TipoCierre.retiro_empresa]))
    def liberar(self, datos, tipo):
        vivas = [a for a in self.asignaciones() if a.vigente and a.aprobada is not False]
        if vivas:
            a = datos.draw(st.sampled_from(vivas))
            self.orq.liberar(a.joven_id, a.vacante_id, tipo, "motivo")

    @rule(v=st.sampled_from(VACANTES), dado=st.integers(0, 5))
    def cerrar(self, v, dado):
        if dado == 0:   # cerrar es definitivo: que ocurra de vez en cuando, no a cada rato
            self.intentar(self.orq.cerrar_vacante, v, "motivo")

    @rule(j=st.sampled_from(JOVENES), v=st.sampled_from(VACANTES))
    def match_y_aprobar(self, j, v):
        """Atajo hacia la parte interesante: interés mutuo, matching y aprobación."""
        self.interes_mutuo(j, v)
        self.orq.ejecutar_matching()
        a = self.orq.almacen.obtener(Asignacion, f"{j}|{v}")
        if a is not None and a.vigente and a.aprobada is None:
            self.orq.orientador_decidir(j, v, True)

    @rule(datos=st.data())
    def reprogramar(self, datos):
        aprobadas = [a for a in self.asignaciones() if a.vigente and a.aprobada]
        if aprobadas:
            a = datos.draw(st.sampled_from(aprobadas))
            self.intentar(self.orq.reprogramar_entrevista, a.joven_id, a.vacante_id, "motivo")

    # ---------- reglas del negocio que deben cumplirse SIEMPRE ----------
    @invariant()
    def cupos_respetados(self):
        vacantes = {v.id: v for v in self.orq.almacen.listar(Vacante)}
        vivas = Counter(a.vacante_id for a in self.asignaciones() if a.vigente and a.aprobada is not False)
        for v, n in vivas.items():
            assert n <= vacantes[v].cupos, f"{v}: {n} asignaciones vivas con {vacantes[v].cupos} cupos"

    @invariant()
    def un_joven_una_asignacion_viva(self):
        vivas = Counter(a.joven_id for a in self.asignaciones() if a.vigente and a.aprobada is not False)
        assert all(n == 1 for n in vivas.values()), vivas

    @invariant()
    def aprobadas_con_entrevista_sin_choques(self):
        aprobadas = [a for a in self.asignaciones() if a.vigente and a.aprobada]
        assert all(a.entrevista is not None for a in aprobadas)
        horarios = Counter((a.vacante_id, a.entrevista) for a in aprobadas)
        assert all(n == 1 for n in horarios.values()), horarios

    @invariant()
    def pendientes_factibles_y_con_interes_mutuo(self):
        mutuos = self.orq.almacen.interes_mutuo()
        for a in self.asignaciones():
            if a.vigente and a.aprobada is None:
                j = self.orq.almacen.obtener(Joven, a.joven_id)
                v = self.orq.almacen.obtener(Vacante, a.vacante_id)
                assert (a.joven_id, a.vacante_id) in mutuos
                assert v.estado == EstadoVacante.publicada
                assert motivos_infactible(j, v, self.orq.matriz()) == []

    @invariant()
    def nada_vivo_en_vacantes_cerradas_o_bloqueadas(self):
        estado = {v.id: v.estado for v in self.orq.almacen.listar(Vacante)}
        for a in self.asignaciones():
            if a.vigente and a.aprobada is not False:
                assert estado[a.vacante_id] in (EstadoVacante.publicada,), (a, estado[a.vacante_id])

    @invariant()
    def plan_solo_para_quien_no_tiene_vacantes(self):
        vacantes = self.orq.almacen.listar(Vacante)
        for p in self.orq.almacen.listar(PlanFormacion):
            j = self.orq.almacen.obtener(Joven, p.joven_id)
            assert not ranking_para_joven(j, vacantes, self.orq.matriz()) or p.cursos == []


Recorridos.TestCase.settings = settings(max_examples=300, stateful_step_count=50, deadline=None,
                                        suppress_health_check=[HealthCheck.too_slow])
TestRecorridos = Recorridos.TestCase


class RecorridosAutomaticos(Recorridos):
    """Los mismos recorridos con el matching automático encendido (como en la API)."""

    def __init__(self):
        super().__init__()
        self.orq.automatico = True


RecorridosAutomaticos.TestCase.settings = settings(max_examples=150, stateful_step_count=40, deadline=None,
                                                   suppress_health_check=[HealthCheck.too_slow])
TestRecorridosAutomaticos = RecorridosAutomaticos.TestCase
