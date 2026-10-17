"""Errores del agente de Mercado.

Una oferta que el texto no permite completar **no se publica en silencio**: se
levanta un error controlado para que el humano la revise y complete los datos.
"""
from __future__ import annotations


class ErrorMercado(Exception):
    """La oferta no se pudo convertir en una `Vacante` válida."""


class OfertaIncompleta(ErrorMercado):
    """Faltan datos que el contrato exige y el texto no permitió deducir.

    `campos` nombra exactamente qué falta, para la revisión humana. El contrato no
    admite valores "desconocidos" en `turnos`, `salario_mensual` ni `corregimiento`,
    así que en esos casos no se devuelve una `Vacante` parcial.
    """

    def __init__(self, campos: list[str]):
        self.campos = sorted(set(campos))
        super().__init__("Faltan datos de la oferta: " + ", ".join(self.campos))