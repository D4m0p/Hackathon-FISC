"""Utilidades de texto deterministas: normalizar, comprobar evidencia, detectar inyección."""
from __future__ import annotations

import re
import unicodedata

_INYECCION = [
    r"ignor[ae]\w* (todas? )?(las |tus |sus )?(instrucciones|indicaciones|reglas)",
    r"ignore (all |any |the )?(previous |prior )?instructions",
    r"olvid[ae]\w* (todo|las instrucciones)",
    r"(eres|act[uú]a como|ahora eres) (un|una) ",
    r"you are now",
    r"system prompt|prompt del sistema",
    r"</?(cv|respuesta|system|instrucciones)>",
    r"(asigna|otorga|agrega|devuelve)\w* (todas las|todas sus|nivel 3)",
]


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto)
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


def _palabras(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9ñ]+", normalizar(texto))


def evidencia_en_texto(evidencia: str, texto: str) -> bool:
    """La evidencia debe salir del texto: cita literal (normalizada) o, si el LLM
    la recortó, al menos 80 % de sus palabras significativas presentes."""
    ev, tx = normalizar(evidencia), normalizar(texto)
    if len(ev) < 3:
        return False
    if ev in tx:
        return True
    significativas = [p for p in _palabras(ev) if len(p) > 3]
    if len(significativas) < 2:
        return False
    presentes = set(_palabras(tx))
    return sum(p in presentes for p in significativas) / len(significativas) >= 0.8


def alertas_inyeccion(texto: str) -> list[str]:
    """Frases que parecen instrucciones al modelo. No bloquean: el texto se sigue
    tratando como dato, pero queda constancia."""
    t = normalizar(texto)
    return [m.group(0) for p in _INYECCION if (m := re.search(p, t))]


def neutralizar(texto: str) -> str:
    """Quita etiquetas que podrían cerrar el delimitador del prompt."""
    return re.sub(r"</?\s*(cv|respuesta|respuestas|system|instrucciones)\s*>", " ", texto, flags=re.I)


def oraciones(texto: str) -> list[str]:
    return [o.strip() for o in re.split(r"[.\n;•·]+", texto) if o.strip()]
