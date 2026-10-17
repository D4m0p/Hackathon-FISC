"""Agente de Mercado (C).

`arranque.agente_real("agentes.mercado", "Mercado")` busca la clase `Mercado`
aquí. También se exponen la taxonomía existente y las funciones de tendencias.
"""
from .agente import Mercado
from .errores import ErrorMercado, OfertaIncompleta
from .taxonomia import cargar_referencia
from .tendencias import tendencias_por_zona, vacantes_por_zona

__all__ = ["ErrorMercado", "Mercado", "OfertaIncompleta", "cargar_referencia",
           "tendencias_por_zona", "vacantes_por_zona"]