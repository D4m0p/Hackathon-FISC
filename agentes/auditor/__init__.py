"""Agente Auditor: clasifica ofertas y audita el matching con contrafactuales.

Implementa `AgenteAuditor` de `orquestador/interfaces.py`. La decisión de bloquear
una oferta la toman las reglas en código de `detector.py`; las pruebas del matching
viven en `contrafactual.py` y también son código determinístico. Un modelo de
lenguaje solo podrá dar una segunda opinión, nunca decidir por sí solo.

La detección es orientativa, no un dictamen legal. El orientador humano puede
publicar una oferta bloqueada si la revisa y deja el motivo.
"""
from __future__ import annotations

from contrato.modelos import DatosPersonales, Joven, Pesos, ResultadoAuditoria, Vacante

from .contrafactual import (
    contrafactual_asignacion_global, corregimientos_de, hallazgos_de_joven, validar_entradas,
)
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

    def auditar_matching(self, resultado, jovenes: list[Joven],
                         datos: dict[str, DatosPersonales], vacantes: list[Vacante],
                         matriz, pesos: Pesos | None = None) -> list[ResultadoAuditoria]:
        """Contrafactuales por joven y validación global del resultado del matching.

        - Por joven: guarda estructural de identidad y contrafactual de corregimiento.
        - Global (solo si hay `resultado`): integridad de asignaciones y desgloses.

        Falla rápido si falta la matriz para evaluar; no convierte un error en una
        auditoría aprobada. Los errores inesperados se dejan propagar.
        """
        validar_entradas(vacantes, matriz)
        corregimientos = corregimientos_de(jovenes, vacantes)
        resultados = []
        for joven in sorted(jovenes, key=lambda j: j.id):
            hallazgos = hallazgos_de_joven(joven, vacantes, matriz, pesos, corregimientos)
            resultados.append(ResultadoAuditoria(
                tipo="contrafactual", objeto_id=joven.id,
                aprobado=not hallazgos, hallazgos=hallazgos))

        if resultado is not None:
            globales = contrafactual_asignacion_global(resultado, jovenes, vacantes, matriz, pesos)
            resultados.append(ResultadoAuditoria(
                tipo="contrafactual", objeto_id="asignacion_global",
                aprobado=not globales, hallazgos=globales))
        return resultados
