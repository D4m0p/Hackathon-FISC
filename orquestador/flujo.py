"""Orquestador: conecta los agentes y deja traza de cada decisión.

Flujo:
  Empresa  → Mercado (normaliza) → Auditor (aprueba o bloquea) → publicada | bloqueada
  Joven    → Perfil (fuera de aquí) → registrar_joven
  Ambos deslizan → interés mutuo → Matching (solver) → Auditor (contrafactuales)
           → Orientador aprueba/rechaza → acción: agenda entrevista y envía mensaje
  Sin asignación → Ruta de formación
"""
from __future__ import annotations

import functools
import inspect
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel

from agentes.auditor.contrafactual import desgloses_de_joven, hallazgos_de_joven
from agentes.formacion import casi_califica, planificar_grupo
from agentes.mercado.tendencias import tendencias_por_zona, vacantes_por_zona
from agentes.matching import (
    MatrizTraslados, asignar, es_factible, motivos_infactible, ranking_para_joven, ranking_para_vacante,
    tiene_alguna_factible,
)
from agentes.matching.traslados import coordenadas_osm
from contrato.modelos import (
    Agente, Asignacion, CasiCalifica, Curso, DatosPersonales, Desglose, EstadoVacante, Habilidad, Hallazgo,
    Joven, Pesos, PlanFormacion, ResultadoAuditoria, ResultadoMatching, TipoCierre, Traza, Vacante,
)

from .agenda import proxima_entrevista
from .almacen import Almacen, clave_asignacion
from .interfaces import AgenteAuditor, AgenteMercado, Notificador, es_oferta_incompleta, faltantes_de
from .notificador import NotificadorRegistro
from .provisionales import AuditorProvisional, MercadoProvisional


class HistoriaJoven(BaseModel):
    """Todo lo que el sistema hizo con un joven, de punta a punta."""
    joven: Joven
    estado: str                         # una frase con dónde está hoy
    asignaciones: list[Asignacion]
    plan: PlanFormacion | None
    deslizamientos: list[dict]
    eventos: list[Traza]                # cronológico: qué agente decidió qué y por qué
    reservas: list[dict] = []           # cupos reservados en cursos: [{curso_id, fecha}]


class CambioPropuesto(BaseModel):
    joven_id: str
    vacante_id: str
    total_actual: float | None   # None = hoy no se propone
    total_nuevo: float | None    # None = con los pesos nuevos no se propondría


class Simulacion(BaseModel):
    """Qué cambiaría en las propuestas si se usaran otros pesos (no se guarda nada)."""
    pesos_actuales: Pesos
    pesos_nuevos: Pesos
    entran: list[CambioPropuesto]
    salen: list[CambioPropuesto]
    se_mantienen: int


class Componentes(BaseModel):
    habilidades: float
    traslado: float
    salario: float
    total: float


def _componentes(d: Desglose) -> Componentes:
    return Componentes(habilidades=d.habilidades, traslado=d.traslado, salario=d.salario, total=d.total)


class VarianteLugar(BaseModel):
    corregimiento: str
    factible: bool
    componentes: Componentes | None = None
    habilidades_igual: bool | None = None   # None si en ese lugar la vacante no es factible


class FilaContrafactual(BaseModel):
    vacante_id: str
    titulo: str
    original: Componentes
    variantes: list[VarianteLugar]


class DemostracionContrafactual(BaseModel):
    """La escena del Auditor: el mismo joven en otros lugares; nombre y género, fuera del solver."""
    joven_id: str
    corregimiento: str
    veredicto: Literal["sin_sesgo", "revisar"]
    hallazgos: list[Hallazgo]
    identidad: str
    campos_que_ve_el_solver: list[str]
    filas: list[FilaContrafactual]


class HabilidadPedida(BaseModel):
    codigo: str
    nombre: str
    vacantes: int


class Tendencias(BaseModel):
    por_zona: dict[str, list[HabilidadPedida]]
    vacantes_por_zona: dict[str, int]
    total_vacantes: int
    nota: str


class VacanteAbierta(BaseModel):
    vacante_id: str
    titulo: str


class Interesado(BaseModel):
    """Un joven al que el curso le sirve, sin datos personales (lo ve el centro)."""
    joven_id: str
    corregimiento: str
    en_plan: bool
    vacantes_que_abre: list[VacanteAbierta]
    minutos: int | None
    costo_semanal: float | None
    cabe_en_horario: bool
    motivo: str


class ReservaVista(BaseModel):
    joven_id: str
    fecha: str


class DemandaCurso(BaseModel):
    curso: Curso
    reservas: list[ReservaVista]
    interesados: list[Interesado]


class Reserva(BaseModel):
    joven_id: str
    curso_id: str
    fecha: str


class ErrorDeFlujo(ValueError):
    """Operación no permitida por las reglas del flujo (la API responde 400)."""


class NoEncontrado(ErrorDeFlujo):
    """El joven, la vacante o la asignación no existe (la API responde 404)."""


def _exclusivo(metodo):
    """Las operaciones que cambian el estado se ejecutan de a una: evita, por ejemplo,
    que dos aprobaciones simultáneas de la misma asignación pasen las dos.

    Los avisos (Telegram) que genera la operación se envían AL SOLTAR el candado: un
    envío lento no deja al resto del sistema esperando. Con llamadas anidadas, envía
    solo la más externa."""
    @functools.wraps(metodo)
    def envoltura(self, *args, **kwargs):
        local = self._local
        profundidad = getattr(local, "profundidad", 0)
        if profundidad == 0:
            local.avisos = []
        local.profundidad = profundidad + 1
        try:
            with self._candado:
                return metodo(self, *args, **kwargs)
        finally:
            local.profundidad = profundidad
            if profundidad == 0:
                avisos, local.avisos = local.avisos, []
                self._enviar_avisos(avisos)
    return envoltura


def _json(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_json(x) for x in obj]
    return obj


class Orquestador:
    def __init__(self, almacen: Almacen, mercado: AgenteMercado | None = None,
                 auditor: AgenteAuditor | None = None, notificador: Notificador | None = None,
                 reloj: Callable[[], datetime] | None = None, automatico: bool = False):
        """`automatico`: el matching se dispara solo (vacante publicada, joven nuevo, interés
        mutuo). La API lo enciende; la carga de datos de demo y las pruebas lo dejan apagado."""
        self.almacen = almacen
        self.automatico = automatico
        self.mercado = mercado or MercadoProvisional()
        self.auditor = auditor or AuditorProvisional()
        self.notificador = notificador or NotificadorRegistro()
        self.reloj = reloj or (lambda: datetime.now(timezone.utc))
        self._candado = threading.RLock()
        self._local = threading.local()   # avisos pendientes de la operación en curso

    # ---------- utilidades ----------
    def _traza(self, agente: Agente, accion: str, motivo: str,
               entrada: dict | None = None, salida: dict | None = None) -> None:
        self.almacen.registrar_traza(Traza(
            agente=agente, accion=accion, motivo=motivo, fecha=self.reloj(),
            entrada={k: _json(v) for k, v in (entrada or {}).items()},
            salida={k: _json(v) for k, v in (salida or {}).items()}))

    def matriz(self) -> MatrizTraslados:
        # con las coordenadas de OpenStreetMap, un viaje que falta en la tabla se estima por distancia
        return MatrizTraslados(self.almacen.traslados(), coordenadas_osm())

    def pesos(self) -> Pesos:
        return self.almacen.obtener(Pesos, "pesos") or Pesos()

    def _joven(self, joven_id: str) -> Joven:
        j = self.almacen.obtener(Joven, joven_id)
        if j is None:
            raise NoEncontrado(f"No existe el joven {joven_id}")
        return j

    def _vacante(self, vacante_id: str) -> Vacante:
        v = self.almacen.obtener(Vacante, vacante_id)
        if v is None:
            raise NoEncontrado(f"No existe la vacante {vacante_id}")
        return v

    # ---------- empresas ----------
    def publicar_oferta(self, texto: str, empresa_id: str) -> tuple[Vacante, ResultadoAuditoria]:
        try:
            vacante = self.mercado.normalizar_oferta(texto, empresa_id)
        except Exception as e:
            if es_oferta_incompleta(e):
                self._traza(Agente.mercado, "oferta_incompleta", str(e),
                            entrada={"empresa_id": empresa_id, "texto": texto[:500]},
                            salida={"faltantes": faltantes_de(e)})
            raise
        self._traza(Agente.mercado, "normalizar_oferta",
                    f"Oferta normalizada con {len(vacante.habilidades_requeridas)} habilidades",
                    entrada={"empresa_id": empresa_id, "texto": texto[:500]},
                    salida={"vacante": vacante})
        return self.publicar_vacante(vacante)

    def _aprobadas_vivas(self, vacante_id: str) -> list[Asignacion]:
        return [a for a in self.almacen.asignaciones(vacante_id=vacante_id) if a.vigente and a.aprobada]

    def _retirar_pendientes(self, motivo: str, joven_id: str | None = None,
                            vacante_id: str | None = None) -> None:
        """Una propuesta pendiente se basa en datos que acaban de cambiar: se retira y el
        próximo matching la recalcula con los datos nuevos."""
        for a in self.almacen.asignaciones(joven_id=joven_id, vacante_id=vacante_id):
            if a.vigente and a.aprobada is None:
                self.almacen.borrar(Asignacion, clave_asignacion(a))
                self._traza(Agente.orquestador, "retirar_propuesta", motivo,
                            entrada={"joven_id": a.joven_id, "vacante_id": a.vacante_id})

    @_exclusivo
    def publicar_vacante(self, vacante: Vacante) -> tuple[Vacante, ResultadoAuditoria]:
        """Toda vacante pasa por el Auditor antes de publicarse, también al corregirla.

        Si ya tiene personas aprobadas, la edición no puede dejarlas mal: se rechaza (y
        queda la versión anterior) si baja los cupos por debajo de ellas, si alguna deja
        de cumplir las condiciones o si el Auditor la bloquea.
        """
        aprobadas = self._aprobadas_vivas(vacante.id)
        if aprobadas:
            if vacante.cupos < len(aprobadas):
                raise ErrorDeFlujo(f"La vacante ya tiene {len(aprobadas)} persona(s) aprobada(s); "
                                   f"no puede bajar a {vacante.cupos} cupo(s)")
            matriz = self.matriz()
            for a in aprobadas:
                motivos = motivos_infactible(self._joven(a.joven_id), vacante, matriz)
                if motivos:
                    raise ErrorDeFlujo(f"La edición deja sin cumplir condiciones a {a.joven_id}, "
                                       f"ya aprobado: {'; '.join(motivos)}")
        resultado = self.auditor.auditar_oferta(vacante)
        if aprobadas and not resultado.aprobado:
            self._traza(Agente.auditor, "auditar_oferta",
                        "Edición rechazada (hay personas aprobadas): "
                        + "; ".join(h.detalle for h in resultado.hallazgos),
                        entrada={"vacante_id": vacante.id}, salida={"resultado": resultado})
            raise ErrorDeFlujo("La edición tiene requisitos discriminatorios y la vacante ya tiene "
                               "personas aprobadas; se mantiene la versión anterior: "
                               + "; ".join(h.detalle for h in resultado.hallazgos))
        estado = EstadoVacante.publicada if resultado.aprobado else EstadoVacante.bloqueada
        existia = self.almacen.obtener(Vacante, vacante.id) is not None
        vacante = vacante.model_copy(update={"estado": estado})
        self.almacen.guardar(vacante)
        if existia:
            self._retirar_pendientes("La vacante cambió", vacante_id=vacante.id)
        if isinstance(self.auditor, AuditorProvisional):
            motivo = "Auditor provisional: publicada sin auditoría real"
        elif resultado.aprobado:
            motivo = "Sin requisitos discriminatorios"
        else:
            motivo = "Bloqueada: " + "; ".join(h.detalle for h in resultado.hallazgos)
        self._traza(Agente.auditor, "auditar_oferta", motivo,
                    entrada={"vacante_id": vacante.id}, salida={"resultado": resultado})
        if estado == EstadoVacante.publicada:
            self._automatico("vacante_publicada", vacante.id, f"Se publicó «{vacante.titulo}»")
        return vacante, resultado

    @_exclusivo
    def orientador_publicar_bloqueada(self, vacante_id: str, motivo: str) -> Vacante:
        """El humano puede corregir un falso positivo del Auditor, siempre con motivo."""
        if not motivo.strip():
            raise ErrorDeFlujo("Para publicar una oferta bloqueada hace falta un motivo")
        vacante = self._vacante(vacante_id)
        if vacante.estado != EstadoVacante.bloqueada:
            raise ErrorDeFlujo("La vacante no está bloqueada")
        vacante = vacante.model_copy(update={"estado": EstadoVacante.publicada})
        self.almacen.guardar(vacante)
        self._traza(Agente.orientador, "publicar_bloqueada", motivo, entrada={"vacante_id": vacante_id})
        self._automatico("vacante_publicada", vacante.id, f"Se publicó «{vacante.titulo}»")
        return vacante

    # ---------- jóvenes ----------
    @_exclusivo
    def registrar_joven(self, joven: Joven, datos: DatosPersonales | None = None) -> Joven:
        if datos is not None and datos.joven_id != joven.id:
            raise ErrorDeFlujo("Los datos personales no corresponden al joven")
        existia = self.almacen.obtener(Joven, joven.id) is not None
        self.almacen.guardar(joven)
        if existia:
            self._retirar_pendientes("El perfil del joven cambió", joven_id=joven.id)
            matriz = self.matriz()
            for a in self.almacen.asignaciones(joven_id=joven.id):
                if a.vigente and a.aprobada:
                    motivos = motivos_infactible(joven, self._vacante(a.vacante_id), matriz)
                    if motivos:   # se permite editar, pero el orientador debe enterarse
                        self._traza(Agente.orquestador, "advertencia",
                                    f"El perfil nuevo choca con la entrevista aprobada: {'; '.join(motivos)}",
                                    entrada={"joven_id": joven.id, "vacante_id": a.vacante_id})
        if datos is not None:
            self.almacen.guardar(datos)
        self._traza(Agente.perfil, "registrar_joven",
                    f"Perfil con {len(joven.habilidades)} habilidades",
                    entrada={"joven_id": joven.id},
                    salida={"habilidades": [h.codigo for h in joven.habilidades]})
        if not existia:
            self._automatico("joven_nuevo", joven.id, f"Se registró {joven.id}")
        return joven

    # ---------- tarjetas y deslizamientos ----------
    def tarjetas_joven(self, joven_id: str) -> list[tuple[Vacante, Desglose]]:
        joven = self._joven(joven_id)
        tarjetas = ranking_para_joven(joven, self.almacen.listar(Vacante), self.matriz(), self.pesos())
        ya = self.almacen.deslizadas_por_joven(joven_id)
        return [(v, d) for v, d in tarjetas if v.id not in ya]

    def tarjetas_vacante(self, vacante_id: str) -> list[tuple[Joven, Desglose]]:
        vacante = self._vacante(vacante_id)
        tarjetas = ranking_para_vacante(vacante, self.almacen.listar(Joven), self.matriz(), self.pesos())
        ya = self.almacen.deslizados_por_empresa(vacante_id)
        return [(j, d) for j, d in tarjetas if j.id not in ya]

    @_exclusivo
    def deslizar(self, actor: str, joven_id: str, vacante_id: str, le_interesa: bool) -> bool:
        """Devuelve True si con este deslizamiento hay interés mutuo."""
        if actor not in ("joven", "empresa"):
            raise ErrorDeFlujo("actor debe ser 'joven' o 'empresa'")
        joven, vacante = self._joven(joven_id), self._vacante(vacante_id)
        if vacante.estado != EstadoVacante.publicada:
            raise ErrorDeFlujo("La vacante no está publicada")
        if not es_factible(joven, vacante, self.matriz()):
            raise ErrorDeFlujo("Ese par no es factible; no aparece en las tarjetas")
        if any(a.joven_id == joven_id for a in self._aprobadas_vivas(vacante_id)):
            raise ErrorDeFlujo("Ya hay una entrevista aprobada para este par; para dejarla, cancélela")
        self.almacen.deslizar(actor, joven_id, vacante_id, le_interesa)
        if not le_interesa:
            self._retirar_pendientes(f"{actor.capitalize()} cambió su respuesta a no",
                                     joven_id=joven_id, vacante_id=vacante_id)
        mutuo = self.almacen.hay_interes_mutuo(joven_id, vacante_id)
        if mutuo and le_interesa:
            self._traza(Agente.orquestador, "interes_mutuo", "El joven y la empresa dijeron que sí",
                        entrada={"joven_id": joven_id, "vacante_id": vacante_id})
            self._automatico("interes_mutuo", f"{joven_id}|{vacante_id}",
                             f"{joven_id} y la empresa de {vacante_id} dijeron que sí", joven_id=joven_id)
        return mutuo

    # ---------- autonomía: el sistema actúa solo, el humano sigue aprobando ----------
    def _automatico(self, disparador: str, objeto_id: str, descripcion: str,
                    joven_id: str | None = None) -> None:
        """Reacciona a un cambio sin esperar al orientador. El matching solo empareja pares con
        interés mutuo: con un joven nuevo no hay nada que emparejar todavía, así que en ese caso
        solo se le arma la ruta de formación si no tiene ninguna vacante a su alcance."""
        if not self.automatico:
            return
        entrada = {"disparador": disparador, "objeto_id": objeto_id}
        if disparador == "joven_nuevo":
            joven = self._joven(objeto_id)
            entrada["joven_id"] = joven.id
            vacantes, matriz = self.almacen.listar(Vacante), self.matriz()
            if tiene_alguna_factible(joven, vacantes, matriz):
                motivo = (f"{descripcion}: tiene vacantes a su alcance para revisar; las propuestas "
                          "llegarán solas cuando haya interés mutuo")
            else:
                plan = planificar_grupo([joven], vacantes, self.almacen.listar(Curso), matriz)[0]
                self.almacen.guardar(plan)
                motivo = (f"{descripcion}: ninguna vacante le queda a su alcance; el sistema le armó "
                          f"una ruta de formación con {len(plan.cursos)} curso(s)")
            self._traza(Agente.matching, "auto_matching", motivo, entrada=entrada, salida={"nuevas": []})
            return
        if joven_id:
            entrada["joven_id"] = joven_id
        antes = self._pendientes()
        self.ejecutar_matching(planificar=disparador != "interes_mutuo")
        nuevas = sorted(clave for clave in self._pendientes() if clave not in antes)
        self._traza(Agente.matching, "auto_matching",
                    f"{descripcion}: el sistema buscó candidatos solo. Propuestas nuevas: "
                    + (", ".join(c.replace("|", "→") for c in nuevas) or "ninguna"),
                    entrada=entrada, salida={"nuevas": nuevas})

    # ---------- matching ----------
    def _entradas_matching(self) -> tuple[list[Joven], list[Vacante], set[tuple[str, str]]]:
        """Jóvenes libres, vacantes con cupos restantes y pares permitidos."""
        asignaciones = self.almacen.listar(Asignacion)
        aprobadas = [a for a in asignaciones if a.aprobada and a.vigente]
        # No se vuelve a proponer un par rechazado por el orientador ni uno ya cerrado
        # (cancelación, inasistencia, retiro o vacante cerrada).
        excluidos = {(a.joven_id, a.vacante_id) for a in asignaciones
                     if a.aprobada is False or not a.vigente}
        ocupados = {a.joven_id for a in aprobadas}
        jovenes = [j for j in self.almacen.listar(Joven) if j.id not in ocupados]
        vacantes = []
        for v in self.almacen.listar(Vacante):
            usados = sum(1 for a in aprobadas if a.vacante_id == v.id)
            if v.cupos > usados:
                vacantes.append(v.model_copy(update={"cupos": v.cupos - usados}))
        return jovenes, vacantes, self.almacen.interes_mutuo() - excluidos

    def _auditar_matching(self, resultado, jovenes, datos, vacantes, matriz, pesos):
        """El Auditor recibe los MISMOS pesos que usó el matching. Si su versión todavía
        no acepta `pesos` (transición), se le llama sin ellos."""
        f = self.auditor.auditar_matching
        params = inspect.signature(f).parameters
        acepta = "pesos" in params or any(x.kind == x.VAR_KEYWORD for x in params.values())
        extra = {"pesos": pesos} if acepta else {}
        return f(resultado, jovenes, datos, vacantes, matriz, **extra)

    @_exclusivo
    def ejecutar_matching(self, planificar: bool = True) -> ResultadoMatching:
        """`planificar=False` omite rearmar las rutas de formación: sirve cuando lo único que cambió
        es un interés mutuo (crea propuestas pendientes, que no ocupan cupo ni cambian qué
        vacantes le sirven a cada joven, así que los planes no pueden cambiar)."""
        matriz = self.matriz()
        for a in self.almacen.listar(Asignacion):   # las pendientes vigentes se recalculan
            if a.aprobada is None and a.vigente:
                self.almacen.borrar(Asignacion, clave_asignacion(a))
        jovenes, vacantes, permitidos = self._entradas_matching()

        pesos = self.pesos()
        resultado = asignar(jovenes, vacantes, matriz, permitidos=permitidos, pesos=pesos)
        for a in resultado.asignaciones:
            self.almacen.guardar(a)
            self.almacen.borrar(PlanFormacion, a.joven_id)   # ya no lo necesita
            self._traza(Agente.matching, "asignar", "; ".join(a.desglose.motivos),
                        entrada={"joven_id": a.joven_id, "vacante_id": a.vacante_id},
                        salida={"desglose": a.desglose})
        self._traza(Agente.matching, "resumen",
                    f"{len(resultado.asignaciones)} asignaciones, {len(resultado.sin_asignar)} sin asignar, "
                    f"{len(permitidos)} pares con interés mutuo",
                    salida={"sin_asignar": resultado.sin_asignar})

        datos = {d.joven_id: d for d in self.almacen.listar(DatosPersonales)}
        for r in self._auditar_matching(resultado, jovenes, datos, vacantes, matriz, pesos):
            self._traza(Agente.auditor, "auditar_matching",
                        "Sin sesgo detectado" if r.aprobado else
                        "; ".join(h.detalle for h in r.hallazgos),
                        entrada={"objeto_id": r.objeto_id}, salida={"resultado": r})

        if not planificar:
            return resultado
        # Ruta de formación solo para quien no tiene NINGUNA vacante factible; quien sí
        # tiene pero aún no logró interés mutuo sigue deslizando.
        libres = set(resultado.sin_asignar)
        sin_asignar = [j for j in jovenes if j.id in libres and not tiene_alguna_factible(j, vacantes, matriz)]
        con_plan = {x.id for x in sin_asignar}
        for j in jovenes:
            if j.id not in con_plan:
                self.almacen.borrar(PlanFormacion, j.id)
        cursos = self.almacen.listar(Curso)
        for plan in planificar_grupo(sin_asignar, vacantes, cursos, matriz):
            anterior = self.almacen.obtener(PlanFormacion, plan.joven_id)
            self.almacen.guardar(plan)
            if anterior != plan:   # solo se traza cuando el plan es nuevo o cambió
                self._traza(Agente.formacion, "planificar", "; ".join(plan.motivos),
                            entrada={"joven_id": plan.joven_id}, salida={"plan": plan})
        return resultado

    @_exclusivo
    def orientador_decidir(self, joven_id: str, vacante_id: str, aprobar: bool,
                           motivo: str = "") -> Asignacion:
        asignacion = self.almacen.obtener(Asignacion, f"{joven_id}|{vacante_id}")
        if asignacion is None:
            raise NoEncontrado("No hay una asignación pendiente para ese par")
        if asignacion.aprobada is not None or not asignacion.vigente:
            raise ErrorDeFlujo("Esa asignación ya fue decidida")
        if not aprobar and not motivo.strip():
            raise ErrorDeFlujo("Para rechazar hace falta un motivo")

        if not aprobar:
            asignacion = asignacion.model_copy(update={"aprobada": False, "motivo_orientador": motivo})
            if not self.almacen.decidir_si_pendiente(asignacion):
                raise ErrorDeFlujo("Esa asignación ya fue decidida")
            self._traza(Agente.orientador, "rechazar", motivo,
                        entrada={"joven_id": joven_id, "vacante_id": vacante_id})
            return asignacion

        joven, vacante = self._joven(joven_id), self._vacante(vacante_id)
        entrevista = proxima_entrevista(joven, vacante, self.reloj(), self._ocupados(vacante_id))
        asignacion = asignacion.model_copy(update={
            "aprobada": True, "motivo_orientador": motivo or None, "entrevista": entrevista})
        # Atómico en la base: aunque haya varios procesos, solo uno puede decidir.
        if not self.almacen.decidir_si_pendiente(asignacion):
            raise ErrorDeFlujo("Esa asignación ya fue decidida")
        self._traza(Agente.orientador, "aprobar", motivo or "Aprobada",
                    entrada={"joven_id": joven_id, "vacante_id": vacante_id})

        self._notificar(
            joven_id, f"Tiene una entrevista para «{vacante.titulo}» el "
                      f"{entrevista:%d/%m/%Y a las %H:%M}. Motivo de la selección: "
                      f"{'; '.join(asignacion.desglose.motivos)}",
            traza={"accion": "agendar_y_notificar",
                   "entrada": {"joven_id": joven_id, "vacante_id": vacante_id},
                   "salida": {"entrevista": entrevista.isoformat()}})
        return asignacion

    # ---------- reacomodo ----------
    def _ocupados(self, vacante_id: str) -> set[datetime]:
        return {a.entrevista for a in self.almacen.asignaciones(vacante_id=vacante_id)
                if a.vigente and a.entrevista is not None}

    def _notificar(self, joven_id: str, cuerpo: str, traza: dict | None = None) -> None:
        """Arma el aviso ahora (con los datos de este momento) y lo deja en cola: se envía
        al soltar el candado. `traza`: si se da, se registra después del envío con su resultado."""
        datos = self.almacen.obtener(DatosPersonales, joven_id)
        texto = (f"Hola, {datos.nombre}. " if datos else "Hola. ") + cuerpo
        destino = datos.contacto_telegram if datos else None
        aviso = (destino, texto, traza)
        if getattr(self._local, "profundidad", 0) > 0:
            self._local.avisos.append(aviso)
        else:
            self._enviar_avisos([aviso])

    def _enviar_avisos(self, avisos: list) -> None:
        for destino, texto, traza in avisos:
            try:
                enviado = self.notificador.enviar(destino, texto)
            except Exception:   # un canal caído no debe tumbar la operación ya guardada
                enviado = False
            self.almacen.registrar_mensaje(destino, texto, enviado)
            if traza is not None:
                self._traza(Agente.orquestador, traza["accion"],
                            "Mensaje enviado" if enviado else "Mensaje registrado (sin canal de envío)",
                            entrada=traza["entrada"], salida={**traza["salida"], "enviado": enviado})

    def _vigente(self, joven_id: str, vacante_id: str) -> Asignacion:
        a = self.almacen.obtener(Asignacion, f"{joven_id}|{vacante_id}")
        if a is None:
            raise NoEncontrado("No hay una asignación para ese par")
        if not a.vigente:
            raise ErrorDeFlujo("Esa asignación ya está cerrada")
        if a.aprobada is False:
            raise ErrorDeFlujo("Esa asignación fue rechazada")
        return a

    def _cerrar(self, a: Asignacion, tipo: TipoCierre, motivo: str) -> Asignacion:
        a = a.model_copy(update={"vigente": False, "tipo_cierre": tipo, "motivo_cierre": motivo})
        self.almacen.guardar(a)
        self._traza(Agente.orquestador, "liberar_cupo", f"{tipo.value}: {motivo}",
                    entrada={"joven_id": a.joven_id, "vacante_id": a.vacante_id})
        return a

    def _reacomodar(self, motivo: str, antes: set[str]) -> list[Asignacion]:
        """Vuelve a correr el solver (óptimo global) y devuelve las propuestas nuevas,
        que quedan pendientes del orientador como cualquier otra."""
        self.ejecutar_matching()
        nuevas = [a for a in self.almacen.listar(Asignacion)
                  if a.aprobada is None and a.vigente and clave_asignacion(a) not in antes]
        self._traza(Agente.matching, "reacomodar",
                    f"{motivo}. Propuestas nuevas: " +
                    (", ".join(f"{a.joven_id}→{a.vacante_id}" for a in nuevas) or "ninguna"),
                    salida={"nuevas": [clave_asignacion(a) for a in nuevas]})
        return nuevas

    def _pendientes(self) -> set[str]:
        return {clave_asignacion(a) for a in self.almacen.listar(Asignacion)
                if a.aprobada is None and a.vigente}

    @_exclusivo
    def liberar(self, joven_id: str, vacante_id: str, tipo: TipoCierre,
                motivo: str) -> tuple[Asignacion, list[Asignacion]]:
        """El joven cancela, no se presenta o la empresa lo retira: el cupo se libera
        y el sistema propone reemplazo de inmediato."""
        if tipo == TipoCierre.vacante_cerrada:
            raise ErrorDeFlujo("Para cerrar una vacante use cerrar_vacante")
        if not motivo.strip():
            raise ErrorDeFlujo("Para liberar un cupo hace falta un motivo")
        antes = self._pendientes()
        cerrada = self._cerrar(self._vigente(joven_id, vacante_id), tipo, motivo)
        if tipo == TipoCierre.retiro_empresa and cerrada.aprobada:
            self._notificar(joven_id, f"La empresa canceló el proceso para «{self._vacante(vacante_id).titulo}». "
                                      "Seguimos buscando otra opción para usted.")
        return cerrada, self._reacomodar(f"Cupo liberado en {vacante_id} ({tipo.value})", antes)

    @_exclusivo
    def cerrar_vacante(self, vacante_id: str, motivo: str) -> tuple[Vacante, list[Asignacion], list[Asignacion]]:
        """La empresa cierra la vacante: sus asignaciones vigentes se cierran, se avisa a
        quienes ya tenían entrevista y se buscan otras opciones para ellos."""
        if not motivo.strip():
            raise ErrorDeFlujo("Para cerrar una vacante hace falta un motivo")
        vacante = self._vacante(vacante_id)
        if vacante.estado == EstadoVacante.cerrada:
            raise ErrorDeFlujo("La vacante ya está cerrada")
        antes = self._pendientes()
        vacante = vacante.model_copy(update={"estado": EstadoVacante.cerrada})
        self.almacen.guardar(vacante)
        self._traza(Agente.orquestador, "cerrar_vacante", motivo, entrada={"vacante_id": vacante_id})
        afectadas = []
        for a in self.almacen.asignaciones(vacante_id=vacante_id):
            if a.vigente and a.aprobada is not False:
                afectadas.append(self._cerrar(a, TipoCierre.vacante_cerrada, motivo))
                if a.aprobada:
                    self._notificar(a.joven_id, f"La vacante «{vacante.titulo}» se cerró. "
                                                "Seguimos buscando otra opción para usted.")
        return vacante, afectadas, self._reacomodar(f"Vacante {vacante_id} cerrada", antes)

    @_exclusivo
    def reprogramar_entrevista(self, joven_id: str, vacante_id: str, motivo: str) -> Asignacion:
        """Mueve la entrevista al siguiente espacio libre después de la actual."""
        if not motivo.strip():
            raise ErrorDeFlujo("Para reprogramar hace falta un motivo")
        a = self._vigente(joven_id, vacante_id)
        if not a.aprobada or a.entrevista is None:
            raise ErrorDeFlujo("Solo se reprograma una asignación aprobada con entrevista")
        joven, vacante = self._joven(joven_id), self._vacante(vacante_id)
        if not vacante.turnos & joven.disponibilidad:
            raise ErrorDeFlujo("Su disponibilidad ya no coincide con el horario de la vacante; "
                               "actualice su disponibilidad o cancele la entrevista")
        desde = max(a.entrevista, self.reloj())
        nueva = proxima_entrevista(joven, vacante, desde, self._ocupados(vacante_id))
        a = a.model_copy(update={"entrevista": nueva})
        self.almacen.guardar(a)
        self._notificar(joven_id, f"Su entrevista para «{vacante.titulo}» se movió al "
                                  f"{nueva:%d/%m/%Y a las %H:%M}.")
        self._traza(Agente.orquestador, "reprogramar", motivo,
                    entrada={"joven_id": joven_id, "vacante_id": vacante_id},
                    salida={"entrevista": nueva.isoformat()})
        return a

    # ---------- pesos del puntaje (decisión del orientador) ----------
    @_exclusivo
    def simular_pesos(self, nuevos: Pesos) -> Simulacion:
        """Corre el matching con los pesos actuales y con los nuevos, sin guardar nada."""
        matriz = self.matriz()
        jovenes, vacantes, permitidos = self._entradas_matching()
        actuales = self.pesos()

        def propuestas(p: Pesos) -> dict[tuple[str, str], float]:
            r = asignar(jovenes, vacantes, matriz, permitidos=permitidos, pesos=p)
            return {(a.joven_id, a.vacante_id): a.desglose.total for a in r.asignaciones}

        antes, despues = propuestas(actuales), propuestas(nuevos)
        entran = [CambioPropuesto(joven_id=j, vacante_id=v, total_actual=None, total_nuevo=t)
                  for (j, v), t in sorted(despues.items()) if (j, v) not in antes]
        salen = [CambioPropuesto(joven_id=j, vacante_id=v, total_actual=t, total_nuevo=None)
                 for (j, v), t in sorted(antes.items()) if (j, v) not in despues]
        return Simulacion(pesos_actuales=actuales, pesos_nuevos=nuevos, entran=entran, salen=salen,
                          se_mantienen=len(antes.keys() & despues.keys()))

    @_exclusivo
    def cambiar_pesos(self, nuevos: Pesos, motivo: str) -> Pesos:
        if not motivo.strip():
            raise ErrorDeFlujo("Para cambiar los pesos hace falta un motivo")
        anteriores = self.pesos()
        self.almacen.guardar(nuevos)
        self._traza(Agente.orientador, "cambiar_pesos", motivo,
                    entrada={"antes": anteriores}, salida={"despues": nuevos})
        # Las propuestas pendientes se calcularon con los pesos viejos.
        self._retirar_pendientes("Cambiaron los pesos del puntaje")
        return nuevos

    # ---------- transparencia de los agentes ----------
    def demostrar_contrafactual(self, joven_id: str) -> DemostracionContrafactual:
        """Números para mostrar que el lugar solo mueve traslado y salario, nunca habilidades.
        El veredicto lo da el Auditor (`hallazgos_de_joven`); aquí solo se arma la vista."""
        joven = self._joven(joven_id)
        vacantes = self.almacen.listar(Vacante)
        matriz, pesos = self.matriz(), self.pesos()
        traslados = self.almacen.traslados()
        lugares = sorted({t.origen for t in traslados} | {t.destino for t in traslados}
                         | {joven.corregimiento} | {v.corregimiento for v in vacantes})
        base = desgloses_de_joven(joven, vacantes, matriz, pesos)
        en_otro_lugar = {c: desgloses_de_joven(joven.model_copy(update={"corregimiento": c}), vacantes, matriz, pesos)
                         for c in lugares if c != joven.corregimiento}
        titulos = {v.id: v.titulo for v in vacantes}
        filas = []
        for vid, d in sorted(base.items(), key=lambda par: (-par[1].total, par[0])):
            variantes = []
            for c, otros in en_otro_lugar.items():
                d2 = otros.get(vid)
                variantes.append(VarianteLugar(
                    corregimiento=c, factible=d2 is not None,
                    componentes=_componentes(d2) if d2 else None,
                    habilidades_igual=(abs(d2.habilidades - d.habilidades) < 1e-9) if d2 else None))
            filas.append(FilaContrafactual(vacante_id=vid, titulo=titulos[vid], original=_componentes(d),
                                           variantes=variantes))
        hallazgos = hallazgos_de_joven(joven, vacantes, matriz, pesos, lugares)
        return DemostracionContrafactual(
            joven_id=joven_id, corregimiento=joven.corregimiento,
            veredicto="revisar" if hallazgos else "sin_sesgo", hallazgos=hallazgos,
            identidad=("Nombre, género, edad y contacto no llegan al solver: viven aparte, en "
                       "DatosPersonales. Por diseño, cambiarlos no puede mover el puntaje (es una "
                       "garantía estructural, no una prueba de comportamiento)."),
            campos_que_ve_el_solver=sorted(Joven.model_fields), filas=filas)

    def tendencias(self, top: int = 5) -> Tendencias:
        """Habilidades más pedidas por zona entre las vacantes publicadas (agente de Mercado)."""
        publicadas = [v for v in self.almacen.listar(Vacante) if v.estado == EstadoVacante.publicada]
        taxonomia = {h.codigo: h for h in self.almacen.listar(Habilidad)}
        por_zona = {zona: [HabilidadPedida(codigo=c, nombre=taxonomia[c].nombre, vacantes=n) for c, n in lista]
                    for zona, lista in tendencias_por_zona(publicadas, taxonomia, top).items()}
        return Tendencias(por_zona=por_zona, vacantes_por_zona=vacantes_por_zona(publicadas),
                          total_vacantes=len(publicadas),
                          nota="Calculado sobre las vacantes publicadas en el sistema; con pocas "
                               "vacantes es ilustrativo, no evidencia del mercado.")

    # ---------- centros de formación (tercer lado del mercado) ----------
    def demanda_centro(self, centro: str) -> list[DemandaCurso]:
        """Para cada curso del centro: quiénes lo necesitan, en orden determinístico.
        Interesados = jóvenes con el curso en su plan de formación ∪ jóvenes a los que solo les
        falta una habilidad que el curso otorga (casi califica). Sin los ya reservados."""
        cursos = sorted((c for c in self.almacen.listar(Curso) if c.centro == centro), key=lambda c: c.id)
        if not cursos:
            return []
        matriz = self.matriz()
        vacantes = {v.id: v for v in self.almacen.listar(Vacante)}
        jovenes = self.almacen.listar(Joven)
        planes = {p.joven_id: p for p in self.almacen.listar(PlanFormacion)}
        casi = {j.id: self.casi_califica(j.id) for j in jovenes}
        demanda = []
        for curso in cursos:
            otorga = {h.codigo: h.nivel for h in curso.habilidades_otorgadas}
            reservados = {r["joven_id"]: r["fecha"] for r in self.almacen.reservas(curso_id=curso.id)}
            interesados = []
            for j in jovenes:
                if j.id in reservados:
                    continue
                plan = planes.get(j.id)
                en_plan = bool(plan and curso.id in plan.cursos)
                abre = set(plan.vacantes_objetivo) if en_plan else set()
                for c in casi[j.id]:
                    falla = c.incumplimiento
                    if falla.tipo.value != "habilidad" or falla.codigo not in otorga:
                        continue
                    v = vacantes.get(c.vacante_id)
                    req = next((r for r in v.habilidades_requeridas if r.codigo == falla.codigo), None) if v else None
                    if req and otorga[falla.codigo] >= req.nivel_minimo:
                        abre.add(c.vacante_id)
                if not en_plan and not abre:
                    continue
                viaje = matriz.viaje(j.corregimiento, curso.corregimiento)
                minutos = viaje.minutos if viaje else None
                costo = round(viaje.costo * 2 * curso.sesiones_por_semana, 2) if viaje else None
                cabe = curso.turnos <= j.disponibilidad
                llega = minutos is not None and minutos <= j.max_minutos_traslado
                partes = [f"Le abre {len(abre)} vacante{'s' if len(abre) != 1 else ''}"] if abre else ["Está en su plan de formación"]
                partes.append(f"{minutos} min de su casa" if minutos is not None else "sin datos de traslado")
                if not cabe:
                    partes.append("el horario del curso no le coincide")
                elif not llega and minutos is not None:
                    partes.append(f"queda más lejos de lo que acepta ({j.max_minutos_traslado} min)")
                interesados.append((not (cabe and llega), -len(abre), not en_plan,
                                    minutos if minutos is not None else 10**9, j.id, Interesado(
                    joven_id=j.id, corregimiento=j.corregimiento, en_plan=en_plan,
                    vacantes_que_abre=[VacanteAbierta(vacante_id=vid, titulo=vacantes[vid].titulo)
                                       for vid in sorted(abre) if vid in vacantes],
                    minutos=minutos, costo_semanal=costo, cabe_en_horario=cabe, motivo="; ".join(partes))))
            interesados.sort(key=lambda t: t[:5])
            demanda.append(DemandaCurso(
                curso=curso, reservas=[ReservaVista(joven_id=jid, fecha=f) for jid, f in reservados.items()],
                interesados=[t[5] for t in interesados]))
        return demanda

    @_exclusivo
    def reservar_cupo(self, curso_id: str, joven_id: str, motivo: str = "") -> tuple[Curso, Reserva]:
        """El centro reserva un cupo: descuenta el cupo (atómico), deja traza y avisa al joven."""
        curso = self.almacen.obtener(Curso, curso_id)
        if curso is None:
            raise NoEncontrado(f"No existe el curso {curso_id}")
        self._joven(joven_id)
        estado = self.almacen.reservar(curso_id, joven_id, motivo)
        if estado == "ya_reservado":
            raise ErrorDeFlujo("Ese joven ya tiene un cupo reservado en este curso")
        if estado == "sin_cupos":
            raise ErrorDeFlujo("El curso no tiene cupos disponibles")
        if estado == "sin_curso":
            raise NoEncontrado(f"No existe el curso {curso_id}")
        curso = self.almacen.obtener(Curso, curso_id)
        reserva = next(r for r in self.almacen.reservas(curso_id=curso_id, joven_id=joven_id))
        self._traza(Agente.formacion, "reservar_cupo",
                    f"Centro {curso.centro} reservó cupo en «{curso.nombre}» para {joven_id}"
                    + (f": {motivo}" if motivo.strip() else ""),
                    entrada={"joven_id": joven_id, "curso_id": curso_id},
                    salida={"cupos_disponibles": curso.cupos_disponibles})
        self._notificar(joven_id, f"Tiene un cupo reservado en «{curso.nombre}» ({curso.centro}), "
                                  f"{curso.semanas} semanas. El centro le contactará para empezar.")
        return curso, Reserva(joven_id=joven_id, curso_id=curso_id, fecha=reserva["fecha"])

    def casi_califica(self, joven_id: str) -> list[CasiCalifica]:
        nombres = {h.codigo: h.nombre for h in self.almacen.listar(Habilidad)}
        return casi_califica(self._joven(joven_id), self.almacen.listar(Vacante),
                             self.almacen.listar(Curso), self.matriz(), nombres)

    def historia(self, joven_id: str) -> HistoriaJoven:
        joven = self._joven(joven_id)
        asignaciones = self.almacen.asignaciones(joven_id=joven_id)
        plan = self.plan_de(joven_id)
        aprobada = next((a for a in asignaciones if a.vigente and a.aprobada), None)
        pendiente = next((a for a in asignaciones if a.vigente and a.aprobada is None), None)
        if aprobada:
            titulo = self._vacante(aprobada.vacante_id).titulo
            estado = f"Entrevista agendada para «{titulo}» el {aprobada.entrevista:%d/%m/%Y a las %H:%M}"
        elif pendiente:
            titulo = self._vacante(pendiente.vacante_id).titulo
            estado = f"Propuesto para «{titulo}», pendiente de aprobación del orientador"
        elif plan and plan.cursos:
            estado = f"Sin vacante factible por ahora: en ruta de formación ({len(plan.cursos)} curso(s))"
        else:
            n = len(self.tarjetas_joven(joven_id))
            estado = f"Buscando: tiene {n} vacante(s) por revisar"
            casi = len(self.casi_califica(joven_id))
            if casi:
                estado += f" y {casi} donde le falta una sola cosa"
        return HistoriaJoven(joven=joven, estado=estado, asignaciones=asignaciones, plan=plan,
                             deslizamientos=self.almacen.deslizamientos_de(joven_id),
                             eventos=self.almacen.trazas_de_joven(joven_id),
                             reservas=[{"curso_id": r["curso_id"], "fecha": r["fecha"]}
                                       for r in self.almacen.reservas(joven_id=joven_id)])

    def plan_de(self, joven_id: str) -> PlanFormacion | None:
        return self.almacen.obtener(PlanFormacion, joven_id)
