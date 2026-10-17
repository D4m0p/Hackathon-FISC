"""Agente de Mercado: oferta en texto libre → `Vacante` en borrador.

Implementa `AgenteMercado` de `orquestador/interfaces.py`. El LLM extrae datos
crudos; este código los valida contra el contrato y contra la taxonomía existente.
Lo que no está en la taxonomía se descarta. La oferta queda en `borrador`: el
Auditor (no este agente) decide si se publica o se bloquea.

Sin `GROQ_API_KEY` el agente sigue funcionando con palabras clave. Si el texto no
permite deducir un campo que el contrato exige (`turnos`, `salario_mensual`,
`corregimiento`), se lanza `OfertaIncompleta` y **no se publica** una oferta
incompleta.
"""
from __future__ import annotations

import re
import uuid
from typing import Callable

from agentes.perfil.llm import ErrorLLM, cliente_desde_entorno
from agentes.perfil.texto import alertas_inyeccion
from contrato.modelos import (
    EstadoVacante, Habilidad, RequisitoHabilidad, Turno, Vacante,
)

from .errores import OfertaIncompleta
from .extraccion import extraer_con_llm, extraer_por_palabras, numero_en_texto, plano
from .taxonomia import cargar_referencia

# Campos que el contrato exige con un valor concreto: no admiten "desconocido".
_OBLIGATORIOS = ("corregimiento", "turnos", "salario_mensual")


class Mercado:
    def __init__(self, taxonomia: dict[str, Habilidad] | None = None,
                 corregimientos: set[str] | None = None,
                 cliente=None, generador_id: Callable[[], str] | None = None,
                 ruta_referencia: str | None = None):
        por_defecto, corregimientos_por_defecto = cargar_referencia(ruta_referencia)
        self.taxonomia = dict(taxonomia) if taxonomia is not None else por_defecto
        self.corregimientos = (set(corregimientos) if corregimientos is not None
                               else corregimientos_por_defecto)
        self.cliente = cliente if cliente is not None else cliente_desde_entorno()
        self.generador_id = generador_id or (lambda: f"v_{uuid.uuid4().hex[:10]}")

    def normalizar_oferta(self, texto: str, empresa_id: str) -> Vacante:
        if not isinstance(texto, str) or not texto.strip():
            raise OfertaIncompleta(["texto"])

        bruto = self._extraer(texto)
        faltan: list[str] = []

        corregimiento = _normalizar_corregimiento(bruto.get("corregimiento"), self.corregimientos)
        if corregimiento is None:
            faltan.append("corregimiento")
        turnos = _normalizar_turnos(bruto.get("turnos"))
        if not turnos:
            faltan.append("turnos")
        salario = _normalizar_salario(bruto.get("salario_mensual"))
        if salario is None:
            faltan.append("salario_mensual")
        if faltan:
            raise OfertaIncompleta(faltan)

        return Vacante(
            id=self.generador_id(), empresa_id=empresa_id,
            titulo=_titulo(bruto.get("titulo"), texto), corregimiento=corregimiento,
            turnos=turnos, dias_por_semana=_entero_en_rango(bruto.get("dias_por_semana"), 1, 7, 5),
            salario_mensual=salario,
            habilidades_requeridas=_normalizar_habilidades(bruto.get("habilidades"), self.taxonomia),
            cupos=_entero_en_rango(bruto.get("cupos"), 1, 1000, 1),
            estado=EstadoVacante.borrador, texto_original=texto)

    def _extraer(self, texto: str) -> dict:
        """Base por palabras clave; encima, lo que devuelva el LLM si está disponible.

        Guardrails: si el texto trae frases que parecen instrucciones al sistema, no se le
        pasa al LLM (solo reglas, que no se pueden manipular). Y el salario del LLM solo se
        acepta si ese número aparece en el texto: un salario inventado no se publica."""
        base = extraer_por_palabras(texto, self.corregimientos)
        if self.cliente is None or alertas_inyeccion(texto):
            return base
        try:
            del_llm = extraer_con_llm(texto, self.cliente)
        except ErrorLLM:
            return base
        salida = _combinar(base, del_llm)
        if not numero_en_texto(_a_numero(salida.get("salario_mensual")), texto):
            salida["salario_mensual"] = base.get("salario_mensual")
        return salida


def _combinar(base: dict, llm: dict) -> dict:
    """Prefiere lo que el LLM sí trajo; conserva el respaldo para lo que dejó vacío."""
    if not isinstance(llm, dict):
        return base
    salida = dict(base)
    for clave in ("titulo", "corregimiento", "salario_mensual", "dias_por_semana", "cupos"):
        valor = llm.get(clave)
        if valor is not None and valor != "":
            salida[clave] = valor
    for clave in ("turnos", "habilidades"):
        valor = llm.get(clave)
        if valor:
            salida[clave] = valor
    return salida


def _titulo(valor, texto: str) -> str:
    if isinstance(valor, str) and valor.strip():
        return _titulo_de_linea(valor.strip())   # el respaldo por reglas trae la línea entera
    for linea in texto.splitlines():
        if linea.strip():
            return _titulo_de_linea(linea.strip())
    return "Oferta sin título"


def _titulo_de_linea(linea: str) -> str:
    """Sin título del LLM: la primera frase de la oferta y, si es larga, hasta la primera coma
    ("Se busca cajera en Arraiján, turno de mañana, …" → "Se busca cajera en Arraiján")."""
    frase = re.split(r"(?<!B/)(?<=[.!?])\s", linea, maxsplit=1)[0]
    if len(frase) > 60:
        coma = frase.find(",")
        if coma >= 15:
            frase = frase[:coma]
    if len(frase) > 80:
        frase = frase[:80].rsplit(" ", 1)[0]
    return frase.strip()


def _normalizar_corregimiento(valor, conocidos: set[str]) -> str | None:
    if not isinstance(valor, str) or not valor.strip():
        return None
    slug = plano(valor).strip().replace(" ", "_")
    return slug if slug in conocidos else None


def _normalizar_turnos(valor) -> set[Turno]:
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, (list, tuple, set)):
        return set()
    validos = {t.value for t in Turno}
    salida = set()
    for t in valor:
        if not isinstance(t, str):
            continue
        clave = plano(t).strip().replace(" ", "_")
        if clave in validos:
            salida.add(Turno(clave))
    return salida


def _normalizar_salario(valor) -> float | None:
    numero = _a_numero(valor)
    if numero is None or numero <= 0:
        return None
    return numero


def _normalizar_habilidades(valor, taxonomia: dict[str, Habilidad]) -> list[RequisitoHabilidad]:
    if not isinstance(valor, list):
        return []
    salida: list[RequisitoHabilidad] = []
    vistos: set[str] = set()
    for item in valor:
        if not isinstance(item, dict):
            continue
        codigo = item.get("codigo")
        if not isinstance(codigo, str) or codigo not in taxonomia or codigo in vistos:
            continue   # fuera de la taxonomía (o repetida): se descarta
        obligatoria = item.get("obligatoria")
        salida.append(RequisitoHabilidad(
            codigo=codigo, nivel_minimo=_entero_en_rango(item.get("nivel_minimo"), 1, 3, 1),
            obligatoria=obligatoria if isinstance(obligatoria, bool) else True))
        vistos.add(codigo)
    return sorted(salida, key=lambda r: r.codigo)


def _entero_en_rango(valor, minimo: int, maximo: int, por_defecto: int) -> int:
    numero = _a_numero(valor)
    if numero is None or not float(numero).is_integer():
        return por_defecto
    entero = int(numero)
    return entero if minimo <= entero <= maximo else por_defecto


def _a_numero(valor) -> float | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        try:
            return float(valor.strip().replace(",", ""))
        except ValueError:
            return None
    return None