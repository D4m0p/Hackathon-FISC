"""Lo que el orquestador espera de cada agente que no es suyo.

Mercado y Auditor (C) implementan estas clases; Perfil (B) entrega `Joven` y
`DatosPersonales` ya construidos a `Orquestador.registrar_joven`.
Mientras no existan, `provisionales.py` trae versiones mínimas.
"""
from __future__ import annotations

from typing import Protocol

from agentes.matching import MatrizTraslados
from contrato.modelos import (
    DatosPersonales, Joven, Pesos, ResultadoAuditoria, ResultadoMatching, Vacante,
)


class OfertaIncompleta(ValueError):
    """El Mercado no pudo armar la vacante: faltan campos obligatorios en la oferta.
    La API responde 422 con `faltantes` para que la empresa los complete."""

    def __init__(self, faltantes: list[str], mensaje: str | None = None):
        self.faltantes = list(faltantes)
        super().__init__(mensaje or "A la oferta le faltan datos: " + ", ".join(self.faltantes))


def es_oferta_incompleta(e: BaseException) -> bool:
    """También acepta una clase propia del Mercado con el mismo nombre (transición)."""
    return isinstance(e, OfertaIncompleta) or type(e).__name__ == "OfertaIncompleta"


def faltantes_de(e: BaseException) -> list[str]:
    for atributo in ("faltantes", "campos", "campos_faltantes", "pendientes"):
        valor = getattr(e, atributo, None)
        if valor:
            return [str(x) for x in valor]
    return []


class AgenteMercado(Protocol):
    def normalizar_oferta(self, texto: str, empresa_id: str) -> Vacante:
        """Texto libre de una oferta → Vacante en estado `borrador`, con
        habilidades normalizadas a la taxonomía y `texto_original` lleno.
        Si faltan campos obligatorios, lanza `OfertaIncompleta(faltantes)`."""


class AgenteAuditor(Protocol):
    def auditar_oferta(self, vacante: Vacante) -> ResultadoAuditoria:
        """`aprobado=False` con hallazgos si hay requisitos discriminatorios."""

    def auditar_matching(self, resultado: ResultadoMatching, jovenes: list[Joven],
                         datos: dict[str, DatosPersonales], vacantes: list[Vacante],
                         matriz: MatrizTraslados, pesos: Pesos | None = None) -> list[ResultadoAuditoria]:
        """Pruebas contrafactuales (nombre, género, corregimiento). `pesos` son los MISMOS
        con que corrió el matching: recalcular con otros daría falsos positivos."""


class Notificador(Protocol):
    def enviar(self, destino: str | None, texto: str) -> bool:
        """Envía un mensaje real (p. ej. Telegram). True si salió."""
