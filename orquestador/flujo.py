"""Orquestador: conecta los agentes y deja traza de cada decisión.

Flujo:
  Empresa  → Mercado (normaliza) → Auditor (aprueba o bloquea) → publicada | bloqueada
  Joven    → Perfil (fuera de aquí) → registrar_joven
  Ambos deslizan → interés mutuo → Matching (solver) → Auditor (contrafactuales)
           → Orientador aprueba/rechaza → acción: agenda entrevista y envía mensaje
  Sin asignación → Ruta de formación
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from agentes.formacion import planificar_grupo
from agentes.matching import MatrizTraslados, asignar, evaluar, ranking_para_joven, ranking_para_vacante
from contrato.modelos import (
    Agente, Asignacion, Curso, DatosPersonales, Desglose, EstadoVacante, Joven, PlanFormacion,
    ResultadoAuditoria, ResultadoMatching, Traza, Vacante,
)

from .agenda import proxima_entrevista
from .almacen import Almacen, clave_asignacion
from .interfaces import AgenteAuditor, AgenteMercado, Notificador
from .notificador import NotificadorRegistro
from .provisionales import AuditorProvisional, MercadoProvisional


class ErrorDeFlujo(ValueError):
    """Operación no permitida por las reglas del flujo (la API la convierte en 4xx)."""


def _json(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_json(x) for x in obj]
    return obj


class Orquestador:
    def __init__(self, almacen: Almacen, mercado: AgenteMercado | None = None,
                 auditor: AgenteAuditor | None = None, notificador: Notificador | None = None,
                 reloj: Callable[[], datetime] | None = None):
        self.almacen = almacen
        self.mercado = mercado or MercadoProvisional()
        self.auditor = auditor or AuditorProvisional()
        self.notificador = notificador or NotificadorRegistro()
        self.reloj = reloj or (lambda: datetime.now(timezone.utc))

    # ---------- utilidades ----------
    def _traza(self, agente: Agente, accion: str, motivo: str,
               entrada: dict | None = None, salida: dict | None = None) -> None:
        self.almacen.registrar_traza(Traza(
            agente=agente, accion=accion, motivo=motivo, fecha=self.reloj(),
            entrada={k: _json(v) for k, v in (entrada or {}).items()},
            salida={k: _json(v) for k, v in (salida or {}).items()}))

    def matriz(self) -> MatrizTraslados:
        return MatrizTraslados(self.almacen.traslados())

    def _joven(self, joven_id: str) -> Joven:
        j = self.almacen.obtener(Joven, joven_id)
        if j is None:
            raise ErrorDeFlujo(f"No existe el joven {joven_id}")
        return j

    def _vacante(self, vacante_id: str) -> Vacante:
        v = self.almacen.obtener(Vacante, vacante_id)
        if v is None:
            raise ErrorDeFlujo(f"No existe la vacante {vacante_id}")
        return v

    # ---------- empresas ----------
    def publicar_oferta(self, texto: str, empresa_id: str) -> tuple[Vacante, ResultadoAuditoria]:
        vacante = self.mercado.normalizar_oferta(texto, empresa_id)
        self._traza(Agente.mercado, "normalizar_oferta",
                    f"Oferta normalizada con {len(vacante.habilidades_requeridas)} habilidades",
                    entrada={"empresa_id": empresa_id, "texto": texto[:500]},
                    salida={"vacante": vacante})
        return self.publicar_vacante(vacante)

    def publicar_vacante(self, vacante: Vacante) -> tuple[Vacante, ResultadoAuditoria]:
        """Toda vacante pasa por el Auditor antes de publicarse, también al corregirla."""
        resultado = self.auditor.auditar_oferta(vacante)
        estado = EstadoVacante.publicada if resultado.aprobado else EstadoVacante.bloqueada
        vacante = vacante.model_copy(update={"estado": estado})
        self.almacen.guardar(vacante)
        if isinstance(self.auditor, AuditorProvisional):
            motivo = "Auditor provisional: publicada sin auditoría real"
        elif resultado.aprobado:
            motivo = "Sin requisitos discriminatorios"
        else:
            motivo = "Bloqueada: " + "; ".join(h.detalle for h in resultado.hallazgos)
        self._traza(Agente.auditor, "auditar_oferta", motivo,
                    entrada={"vacante_id": vacante.id}, salida={"resultado": resultado})
        return vacante, resultado

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
        return vacante

    # ---------- jóvenes ----------
    def registrar_joven(self, joven: Joven, datos: DatosPersonales | None = None) -> Joven:
        if datos is not None and datos.joven_id != joven.id:
            raise ErrorDeFlujo("Los datos personales no corresponden al joven")
        self.almacen.guardar(joven)
        if datos is not None:
            self.almacen.guardar(datos)
        self._traza(Agente.perfil, "registrar_joven",
                    f"Perfil con {len(joven.habilidades)} habilidades",
                    entrada={"joven_id": joven.id},
                    salida={"habilidades": [h.codigo for h in joven.habilidades]})
        return joven

    # ---------- tarjetas y deslizamientos ----------
    def tarjetas_joven(self, joven_id: str) -> list[tuple[Vacante, Desglose]]:
        joven = self._joven(joven_id)
        tarjetas = ranking_para_joven(joven, self.almacen.listar(Vacante), self.matriz())
        return [(v, d) for v, d in tarjetas if not self.almacen.ya_deslizo("joven", joven_id, v.id)]

    def tarjetas_vacante(self, vacante_id: str) -> list[tuple[Joven, Desglose]]:
        vacante = self._vacante(vacante_id)
        tarjetas = ranking_para_vacante(vacante, self.almacen.listar(Joven), self.matriz())
        return [(j, d) for j, d in tarjetas if not self.almacen.ya_deslizo("empresa", j.id, vacante_id)]

    def deslizar(self, actor: str, joven_id: str, vacante_id: str, le_interesa: bool) -> bool:
        """Devuelve True si con este deslizamiento hay interés mutuo."""
        if actor not in ("joven", "empresa"):
            raise ErrorDeFlujo("actor debe ser 'joven' o 'empresa'")
        joven, vacante = self._joven(joven_id), self._vacante(vacante_id)
        if vacante.estado != EstadoVacante.publicada:
            raise ErrorDeFlujo("La vacante no está publicada")
        if not isinstance(evaluar(joven, vacante, self.matriz()), Desglose):
            raise ErrorDeFlujo("Ese par no es factible; no aparece en las tarjetas")
        self.almacen.deslizar(actor, joven_id, vacante_id, le_interesa)
        mutuo = (joven_id, vacante_id) in self.almacen.interes_mutuo()
        if mutuo and le_interesa:
            self._traza(Agente.orquestador, "interes_mutuo", "El joven y la empresa dijeron que sí",
                        entrada={"joven_id": joven_id, "vacante_id": vacante_id})
        return mutuo

    # ---------- matching ----------
    def ejecutar_matching(self) -> ResultadoMatching:
        matriz = self.matriz()
        asignaciones = self.almacen.listar(Asignacion)
        aprobadas = [a for a in asignaciones if a.aprobada]
        rechazadas = {(a.joven_id, a.vacante_id) for a in asignaciones if a.aprobada is False}
        for a in asignaciones:   # las pendientes se recalculan
            if a.aprobada is None:
                self.almacen.borrar(Asignacion, clave_asignacion(a))

        ocupados = {a.joven_id for a in aprobadas}
        jovenes = [j for j in self.almacen.listar(Joven) if j.id not in ocupados]
        vacantes = []
        for v in self.almacen.listar(Vacante):
            usados = sum(1 for a in aprobadas if a.vacante_id == v.id)
            if v.cupos > usados:
                vacantes.append(v.model_copy(update={"cupos": v.cupos - usados}))
        permitidos = self.almacen.interes_mutuo() - rechazadas

        resultado = asignar(jovenes, vacantes, matriz, permitidos=permitidos)
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
        for r in self.auditor.auditar_matching(resultado, jovenes, datos, vacantes, matriz):
            self._traza(Agente.auditor, "auditar_matching",
                        "Sin sesgo detectado" if r.aprobado else
                        "; ".join(h.detalle for h in r.hallazgos),
                        entrada={"objeto_id": r.objeto_id}, salida={"resultado": r})

        sin_asignar = [j for j in jovenes if j.id in set(resultado.sin_asignar)]
        cursos = self.almacen.listar(Curso)
        for plan in planificar_grupo(sin_asignar, vacantes, cursos, matriz):
            self.almacen.guardar(plan)
            self._traza(Agente.formacion, "planificar", "; ".join(plan.motivos),
                        entrada={"joven_id": plan.joven_id}, salida={"plan": plan})
        return resultado

    def orientador_decidir(self, joven_id: str, vacante_id: str, aprobar: bool,
                           motivo: str = "") -> Asignacion:
        asignacion = self.almacen.obtener(Asignacion, f"{joven_id}|{vacante_id}")
        if asignacion is None:
            raise ErrorDeFlujo("No hay una asignación pendiente para ese par")
        if asignacion.aprobada is not None:
            raise ErrorDeFlujo("Esa asignación ya fue decidida")
        if not aprobar and not motivo.strip():
            raise ErrorDeFlujo("Para rechazar hace falta un motivo")

        if not aprobar:
            asignacion = asignacion.model_copy(update={"aprobada": False, "motivo_orientador": motivo})
            self.almacen.guardar(asignacion)
            self._traza(Agente.orientador, "rechazar", motivo,
                        entrada={"joven_id": joven_id, "vacante_id": vacante_id})
            return asignacion

        joven, vacante = self._joven(joven_id), self._vacante(vacante_id)
        ocupados = {a.entrevista for a in self.almacen.listar(Asignacion)
                    if a.vacante_id == vacante_id and a.entrevista is not None}
        entrevista = proxima_entrevista(joven, vacante, self.reloj(), ocupados)
        asignacion = asignacion.model_copy(update={
            "aprobada": True, "motivo_orientador": motivo or None, "entrevista": entrevista})
        self.almacen.guardar(asignacion)
        self._traza(Agente.orientador, "aprobar", motivo or "Aprobada",
                    entrada={"joven_id": joven_id, "vacante_id": vacante_id})

        datos = self.almacen.obtener(DatosPersonales, joven_id)
        saludo = f"Hola, {datos.nombre}." if datos else "Hola."
        texto = (f"{saludo} Tiene una entrevista para «{vacante.titulo}» el "
                 f"{entrevista:%d/%m/%Y a las %H:%M}. Motivo de la selección: "
                 f"{'; '.join(asignacion.desglose.motivos)}")
        enviado = self.notificador.enviar(datos.contacto_telegram if datos else None, texto)
        self.almacen.registrar_mensaje(datos.contacto_telegram if datos else None, texto, enviado)
        self._traza(Agente.orquestador, "agendar_y_notificar",
                    "Mensaje enviado" if enviado else "Mensaje registrado (sin canal de envío)",
                    entrada={"joven_id": joven_id, "vacante_id": vacante_id},
                    salida={"entrevista": entrevista.isoformat(), "enviado": enviado})
        return asignacion

    def plan_de(self, joven_id: str) -> PlanFormacion | None:
        return self.almacen.obtener(PlanFormacion, joven_id)
