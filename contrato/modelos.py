"""Contrato de datos compartido por todos los agentes.

Regla: después de congelarse solo se agregan campos opcionales; nunca se
renombra ni se borra un campo existente.

Los datos personales (nombre, género, edad) viven en `DatosPersonales`, separados
de `Joven`. Los solvers reciben solo `Joven`, así que no pueden usarlos.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ---------- Catálogos ----------

class Turno(str, Enum):
    manana = "manana"
    tarde = "tarde"
    noche = "noche"
    fin_de_semana = "fin_de_semana"


class EstadoVacante(str, Enum):
    borrador = "borrador"
    bloqueada = "bloqueada"      # el Auditor encontró requisitos discriminatorios
    publicada = "publicada"
    cerrada = "cerrada"


class Agente(str, Enum):
    mercado = "mercado"
    perfil = "perfil"
    matching = "matching"
    formacion = "formacion"
    auditor = "auditor"
    orquestador = "orquestador"
    orientador = "orientador"    # la persona humana que aprueba


class Genero(str, Enum):
    femenino = "femenino"
    masculino = "masculino"
    otro = "otro"
    no_indica = "no_indica"


# ---------- Habilidades ----------

class Habilidad(BaseModel):
    """Entrada de la taxonomía (tipo ESCO). La mantiene el agente de Mercado."""
    codigo: str = Field(min_length=1)
    nombre: str = Field(min_length=1)


class HabilidadNivel(BaseModel):
    """Habilidad que tiene una persona u otorga un curso. Nivel 1 básico a 3 avanzado."""
    codigo: str = Field(min_length=1)
    nivel: int = Field(ge=1, le=3)
    evidencia: str | None = None   # de dónde salió (CV, entrevista, curso)


class RequisitoHabilidad(BaseModel):
    codigo: str = Field(min_length=1)
    nivel_minimo: int = Field(default=1, ge=1, le=3)
    obligatoria: bool = True


# ---------- Actores ----------

class Joven(BaseModel):
    """Lo único que ve el solver de una persona: sin nombre, género ni edad."""
    id: str
    corregimiento: str
    disponibilidad: set[Turno] = Field(min_length=1)
    presupuesto_transporte_semanal: float = Field(ge=0)   # B/.
    salario_minimo: float = Field(ge=0)                   # B/. mensual
    max_minutos_traslado: int = Field(default=75, gt=0)   # por viaje
    habilidades: list[HabilidadNivel] = []


class DatosPersonales(BaseModel):
    joven_id: str
    nombre: str
    genero: Genero = Genero.no_indica
    edad: int | None = Field(default=None, ge=14, le=99)
    contacto_telegram: str | None = None


class Vacante(BaseModel):
    id: str
    empresa_id: str
    titulo: str
    corregimiento: str
    turnos: set[Turno] = Field(min_length=1)   # el joven debe tener todos disponibles
    dias_por_semana: int = Field(default=5, ge=1, le=7)
    salario_mensual: float = Field(ge=0)
    habilidades_requeridas: list[RequisitoHabilidad] = []
    cupos: int = Field(default=1, ge=1)
    estado: EstadoVacante = EstadoVacante.borrador
    texto_original: str | None = None


class Curso(BaseModel):
    id: str
    centro: str                       # p. ej. INADEH
    nombre: str
    corregimiento: str
    turnos: set[Turno] = Field(min_length=1)
    sesiones_por_semana: int = Field(ge=1, le=7)
    semanas: int = Field(ge=1)
    costo: float = Field(default=0, ge=0)   # B/. matrícula
    cupos_disponibles: int = Field(ge=0)
    habilidades_otorgadas: list[HabilidadNivel] = Field(min_length=1)


class Traslado(BaseModel):
    """Un viaje de ida entre corregimientos."""
    origen: str
    destino: str
    minutos: int = Field(ge=0)
    costo: float = Field(ge=0)   # B/. por viaje


# ---------- Resultados de los agentes ----------

class Desglose(BaseModel):
    """Explicación de un puntaje: cada componente va de 0 a 1."""
    habilidades: float
    traslado: float
    salario: float
    total: float
    motivos: list[str] = []


class Infactible(BaseModel):
    joven_id: str
    vacante_id: str
    motivos: list[str] = Field(min_length=1)


class Asignacion(BaseModel):
    joven_id: str
    vacante_id: str
    desglose: Desglose
    aprobada: bool | None = None   # None = pendiente del orientador


class ResultadoMatching(BaseModel):
    asignaciones: list[Asignacion]
    sin_asignar: list[str]          # ids de jóvenes
    infactibles: list[Infactible]


class PlanFormacion(BaseModel):
    joven_id: str
    vacantes_objetivo: list[str]
    cursos: list[str]               # ids en orden sugerido
    habilidades_cubiertas: list[str]
    brecha_sin_cubrir: list[str]    # lo que ningún curso factible cubre
    costo_total: float              # matrícula + transporte
    semanas_total: int
    motivos: list[str] = []


class Hallazgo(BaseModel):
    regla: str                      # p. ej. "edad", "buena_presencia", "contrafactual_genero"
    fragmento: str | None = None
    detalle: str
    sugerencia: str | None = None


class ResultadoAuditoria(BaseModel):
    tipo: str                       # "oferta" o "contrafactual"
    objeto_id: str
    aprobado: bool
    hallazgos: list[Hallazgo] = []

    @model_validator(mode="after")
    def _rechazo_con_motivo(self) -> "ResultadoAuditoria":
        if not self.aprobado and not self.hallazgos:
            raise ValueError("un rechazo debe traer al menos un hallazgo")
        return self


class Traza(BaseModel):
    agente: Agente
    accion: str
    entrada: dict[str, Any] = {}
    salida: dict[str, Any] = {}
    motivo: str
    fecha: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
