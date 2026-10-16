"""Lo que el orquestador espera de cada agente que no es suyo.

Mercado y Auditor (C) implementan estas clases; Perfil (B) entrega `Joven` y
`DatosPersonales` ya construidos a `Orquestador.registrar_joven`.
Mientras no existan, `provisionales.py` trae versiones mínimas.
"""
from __future__ import annotations

from typing import Protocol

from agentes.matching import MatrizTraslados
from contrato.modelos import (
    DatosPersonales, Joven, ResultadoAuditoria, ResultadoMatching, Vacante,
)


class AgenteMercado(Protocol):
    def normalizar_oferta(self, texto: str, empresa_id: str) -> Vacante:
        """Texto libre de una oferta → Vacante en estado `borrador`, con
        habilidades normalizadas a la taxonomía y `texto_original` lleno."""


class AgenteAuditor(Protocol):
    def auditar_oferta(self, vacante: Vacante) -> ResultadoAuditoria:
        """`aprobado=False` con hallazgos si hay requisitos discriminatorios."""

    def auditar_matching(self, resultado: ResultadoMatching, jovenes: list[Joven],
                         datos: dict[str, DatosPersonales], vacantes: list[Vacante],
                         matriz: MatrizTraslados) -> list[ResultadoAuditoria]:
        """Pruebas contrafactuales (nombre, género, corregimiento)."""


class Notificador(Protocol):
    def enviar(self, destino: str | None, texto: str) -> bool:
        """Envía un mensaje real (p. ej. Telegram). True si salió."""
