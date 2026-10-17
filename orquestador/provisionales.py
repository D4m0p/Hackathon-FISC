"""Versiones mínimas de Mercado y Auditor para correr el flujo completo mientras
C termina las reales. Se reemplazan pasando las reales al `Orquestador`."""
from __future__ import annotations

from contrato.modelos import ResultadoAuditoria, Vacante

PROVISIONAL = "provisional"


class MercadoProvisional:
    def normalizar_oferta(self, texto: str, empresa_id: str) -> Vacante:
        raise NotImplementedError(
            "El agente de Mercado todavía no está conectado; use publicar_vacante con datos estructurados")


class AuditorProvisional:
    """Aprueba todo; el orquestador deja constancia en la traza de que es provisional."""

    def auditar_oferta(self, vacante: Vacante) -> ResultadoAuditoria:
        return ResultadoAuditoria(tipo="oferta", objeto_id=vacante.id, aprobado=True)

    def auditar_matching(self, resultado, jovenes, datos, vacantes, matriz, pesos=None) -> list[ResultadoAuditoria]:
        return []
