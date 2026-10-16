"""Agente Auditor: clasifica ofertas y (más adelante) audita el matching.

Implementa `AgenteAuditor` de `orquestador/interfaces.py`. La decisión de bloquear
una oferta la toman las reglas en código de `detector.py`; un modelo de lenguaje
solo podrá dar una segunda opinión, nunca decidir por sí solo.

La detección es orientativa, no un dictamen legal. El orientador humano puede
publicar una oferta bloqueada si la revisa y deja el motivo.
"""
from __future__ import annotations

from contrato.modelos import ResultadoAuditoria, Vacante

from .detector import detectar

__all__ = ["Auditor", "detectar"]


class Auditor:
    def __init__(self) -> None:
        pass

    def auditar_oferta(self, vacante: Vacante) -> ResultadoAuditoria:
        """Bloquea la oferta si el título o el texto original traen señales discriminatorias."""
        texto = "\n".join(t for t in (vacante.titulo, vacante.texto_original) if t)
        hallazgos = detectar(texto)
        return ResultadoAuditoria(
            tipo="oferta", objeto_id=vacante.id,
            aprobado=not hallazgos, hallazgos=hallazgos)

    def auditar_matching(self, resultado, jovenes, datos, vacantes, matriz) -> list[ResultadoAuditoria]:
        """Pruebas contrafactuales (nombre, género, corregimiento): paso siguiente.

        Por ahora no emite resultados, igual que el auditor provisional; no se
        inventan aprobaciones.
        """
        return []
