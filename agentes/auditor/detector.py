"""Detector determinístico de lenguaje potencialmente discriminatorio en ofertas.

La decisión de bloquear una oferta se toma aquí, con reglas en código (expresiones
regulares y pequeñas decisiones contextuales). Un modelo de lenguaje podrá dar una
segunda opinión más adelante, pero nunca decidirá por sí solo.

Limitaciones (no se pretende cubrir todos los casos posibles):

- Las reglas son heurísticas y en español; se les escapan variantes poco frecuentes,
  errores ortográficos, texto en otro idioma y evasiones deliberadas.
- El contrato actual no tiene un estado intermedio "pendiente de revisión": solo
  `aprobado` (bool). Por eso toda coincidencia bloquea la oferta y necesita revisión
  humana. Casos a menudo legítimos o matizables también se marcan y quedan a
  criterio del orientador, por ejemplo:
      * "mayor de 21 años" (un mínimo por encima de la mayoría de edad),
      * "residir en Panamá" (referencia geográfica amplia),
      * "se valorará buena presencia" (apariencia como criterio blando).
- Pedir "mayor de 18 años" no se marca: 18 es la mayoría de edad y un mínimo legal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from contrato.modelos import Hallazgo

EDAD_MINIMA_LEGAL = 18

_DETALLE_EDAD = ("Se pide una edad o un rango de edad, que no es un requisito "
                 "justificado para el puesto.")
_SUGERENCIA_EDAD = ("Describa las funciones y competencias necesarias (incluida la "
                    "experiencia) en lugar de la edad.")

_FLAGS = re.IGNORECASE | re.UNICODE

# Adjetivos civiles aislados: en mayúscula suelen ser un nombre propio (la empresa "Casado").
_ADJETIVOS_CIVILES = frozenset({
    "soltero", "soltera", "solteros", "solteras",
    "casado", "casada", "casados", "casadas",
    "viudo", "viuda", "viudos", "viudas",
    "divorciado", "divorciada", "divorciados", "divorciadas",
})
_CUE_REQUISITO = re.compile(
    r"\b(?:sea|ser|debe|deber[áa]|solicit\w+|requer\w+|busc\w+|personal|"
    r"preferiblemente|indispensable|solo|solamente|requisito|estado\s+civil)\b", _FLAGS)


def _predicado_estado_civil(texto: str, coincidencia: re.Match[str]) -> bool:
    """Un adjetivo civil aislado y en mayúscula suele ser un nombre propio (la empresa
    "Casado"); solo lo tratamos como requisito si va en minúscula o tras una señal de
    requisito. "estado civil", "con hijos" y "madres solteras" siempre valen."""
    token = coincidencia.group(0)
    if token.lower() not in _ADJETIVOS_CIVILES:
        return True
    if token[0].islower():
        return True
    antes = texto[max(0, coincidencia.start() - 40):coincidencia.start()]
    return _CUE_REQUISITO.search(antes) is not None


@dataclass(frozen=True)
class Regla:
    nombre: str
    patrones: tuple[str, ...]
    detalle: str
    sugerencia: str
    negacion: bool = False          # ¿descartar la coincidencia si está negada?
    negacion_interna: bool = True   # ¿buscar la negación también dentro de la coincidencia?
    contexto_producto: bool = False # ¿descartar si el contexto es un producto, no un puesto?
    predicado: "Callable[[str, re.Match[str]], bool] | None" = None  # filtro de la coincidencia


_REGLAS: tuple[Regla, ...] = (
    Regla(
        nombre="genero",
        patrones=(
            r"\bfemenin[ao]s?\b",
            r"\bmasculin[ao]s?\b",
            r"sexo\s+(?:femenino|masculino)",
            r"personal\s+(?:femenino|masculino)",
            r"(?:candidat[oa]|postulante|aspirante|aplicante|emplead[oa]|trabajador[ao]?)"
            r"\s+(?:de\s+sexo\s+)?(?:femenino|masculino)",
            r"se\s+(?:busca|requiere|solicita|necesita|contrata|precisa)\s+"
            r"(?:una?\s+|un\s+)?(?:se[ñn]orita|dama|mujer|hombre|var[oó]n|se[ñn]or)\b",
            r"(?:solo|sólo|exclusiv[ao]|únicamente|unicamente)\s+(?:para\s+)?"
            r"(?:mujeres|hombres|damas|caballeros|se[ñn]oritas|varones)\b",
            r"(?:busca|requiere|solicita|necesita|contratar|contrata|personal|puesto|"
            r"cargo|vacante)[^.\n]{0,30}\b(?:dama|se[ñn]orita|var[oó]n)\b",
        ),
        detalle="Se exige o se sugiere un género; la vacante debe estar abierta a "
                "cualquier persona.",
        sugerencia="Elimine toda referencia al género y describa las competencias y "
                   "funciones del puesto.",
        contexto_producto=True,
    ),
    Regla(
        nombre="estado_civil",
        patrones=(
            r"\bestado\s+civil\b",
            r"\bsolter[ao]s?\b",
            r"\bcasad[ao]s?\b",
            r"\b(?:con|sin)\s+hijos?\b",
            r"\b(?:tener|tiene|tenga|tuvo)\s+hijos?\b",
            r"madres?\s+solteras?",
            r"\b(?:viud[ao]|divorciad[ao])s?\b",
        ),
        detalle="El estado civil o la situación familiar no son requisitos del puesto.",
        sugerencia="No incluya el estado civil ni la composición familiar; evalúe las "
                   "competencias.",
        negacion=True,
        negacion_interna=False,   # "sin hijos" es en sí un requisito que debe marcarse
        predicado=_predicado_estado_civil,
    ),
    Regla(
        nombre="foto_obligatoria",
        patrones=(
            r"fotograf[íi]a\s+obligatoria",
            r"foto\s+(?:obligatoria|reciente|de\s+frente|tipo\s+carn[ée]|tama(?:ñ|n)o)",
            r"(?:adjunt|envi|inclu|present|acompañ|remit|carg|requer)\w*\s+"
            r"(?:su\s+|el\s+|la\s+|una\s+)?(?:cv\s+)?(?:con\s+)?fot\w*",
            r"\bcon\s+foto\b",
            r"\bfoto\s*carn[ée]\b",
        ),
        detalle="Pedir una fotografía puede facilitar la discriminación y no mide "
                "competencias para el puesto.",
        sugerencia="Solicite la foto solo si es indispensable para el cargo, en una "
                   "etapa final y no para preseleccionar.",
        negacion=True,
    ),
    Regla(
        nombre="buena_presencia",
        patrones=(
            r"(?:buena|excelente|impecable|agradable|gran)\s+presencia",
            r"presencia\s+(?:impecable|excelente|agradable|buena|sobresaliente)",
            r"buena\s+presencia\s+f[íi]sica",
            r"buen\s+aspecto",
            r"buen\s+porte",
            r"(?:excelente|impecable|buena|agradable)\s+presentaci[oó]n",
            r"apariencia\s+(?:agradable|impecable|f[íi]sica|excelente)",
            r"imagen\s+(?:impecable|agradable|profesional)",
            r"\bbuena\s+imagen\b",
        ),
        detalle="La buena presencia es un requisito subjetivo que puede encubrir "
                "discriminación por apariencia, edad o género.",
        sugerencia="Sustitúyalo por requisitos verificables, por ejemplo presentación "
                   "profesional acorde al uniforme del puesto.",
        negacion=True,
    ),
    Regla(
        nombre="residir_en",
        patrones=(
            r"residir\s+en",
            r"radicar\s+en",
            r"domiciliad[ao]s?\s+en",
            r"que\s+viva(?:n)?\s+en",
            r"vivir\s+en\s+(?:la|el|zona|[áa]rea|ciudad)",
        ),
        detalle="Exigir residir en una zona puede excluir sin justificación a quien "
                "puede trasladarse.",
        sugerencia="Publíquela como preferencia, no como requisito, e indique el tiempo "
                   "de traslado aceptable.",
        negacion=True,
    ),
)

# (patrón, tipo). tipo: "tope" = límite superior, "minimo" = mínimo de edad, "rango",
# "menor" = "menor(es) de N años": tope si N > 18; con N <= 18 es excluir a menores de
# edad, que es legal ("No se aceptan menores de 18 años").
_EDAD_PATRONES: tuple[tuple[str, str], ...] = (
    (r"menor(?:es)?\s+de\s+(\d{1,2})\s+a(?:ñ|n)os", "menor"),
    (r"no\s+mayor(?:es)?\s+de\s+(\d{1,2})\s+a(?:ñ|n)os", "tope"),
    (r"no\s+(?:más|mas)\s+de\s+(\d{1,2})\s+a(?:ñ|n)os", "tope"),
    (r"(?:hasta|máximo|maximo)\s+(\d{1,2})\s+a(?:ñ|n)os", "tope"),
    (r"edad\s+máxima", "tope"),
    (r"mayor(?:es)?\s+de\s+(\d{1,3})\s+a(?:ñ|n)os", "minimo"),
    (r"(?:a\s+partir\s+de|desde)\s+(?:los\s+)?(\d{1,3})\s+a(?:ñ|n)os", "minimo"),
    (r"\b(\d{1,3})\s+a(?:ñ|n)os\s+en\s+adelante", "minimo"),
    (r"edad\s+m[íi]nima\s*(?:de\s*)?(\d{1,3})?", "minimo"),
    (r"entre\s+(\d{1,2})\s+(?:y|a)\s+(\d{1,2})\s+a(?:ñ|n)os(?!\s*,?\s*de\s+experiencia)",
     "rango"),
    (r"de\s+(\d{1,2})\s+a\s+(\d{1,2})\s+a(?:ñ|n)os(?!\s*,?\s*de\s+experiencia)", "rango"),
    (r"(\d{2})\s*[-\u2013]\s*(\d{2})\s+a(?:ñ|n)os(?!\s*,?\s*de\s+experiencia)", "rango"),
)

_COMPILADAS: tuple[tuple[Regla, tuple[re.Pattern[str], ...]], ...] = tuple(
    (regla, tuple(re.compile(p, _FLAGS) for p in regla.patrones)) for regla in _REGLAS
)
_EDAD_COMPILADAS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p, _FLAGS), tipo) for p, tipo in _EDAD_PATRONES
)

# Palabras "de relleno" que pueden ir entre una negación y el requisito.
_RELLENO = frozenset({
    "su", "sus", "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "que", "ser", "tener",
    "necesario", "necesaria", "necesarios", "necesarias",
    "requisito", "requisitos", "obligatorio", "obligatoria", "obligatorios",
    "obligatorias", "indispensable", "indispensables", "importante", "importantes",
    "exige", "exigen", "exigir", "requiere", "requieren", "requerir",
    "solicita", "solicitan", "solicitar", "necesita", "necesitan", "necesitar",
    "permite", "permiten", "permitir", "acepta", "aceptan", "aceptar",
    "pide", "piden", "pedir", "pedimos", "exigimos", "requerimos", "solicitamos",
})
# "ni" continúa una negación anterior: "no se exige buena presencia ni excelente presentación".
_INICIOS_NEGACION = ("no es", "no se", "no importa", "no hace falta", "sin", "tampoco", "ni")
_PALABRA = re.compile(r"[\wáéíóúüñ]+", re.UNICODE)
_PRODUCTO = re.compile(
    r"\b(?:ropa|moda|colecci[oó]n|secci[oó]n|calzado|zapat\w*|prenda\w*|l[íi]nea|"
    r"perfume\w*|colonia\w*|accesorio\w*|cat[áa]logo|joyer[íi]a|bisuter[íi]a|"
    r"tela\w*|p[úu]blico|vestuario|departamento|pasillo)\b", _FLAGS)


def _termina_en_negacion(ventana: str) -> bool:
    """True si la ventana termina en una negación aplicable al requisito."""
    palabras = _PALABRA.findall(ventana.lower())
    while palabras and palabras[-1] in _RELLENO:
        palabras.pop()
    if not palabras:
        return False
    cola = " ".join(palabras[-3:])
    # por palabra completa: "mini" no es "ni", "Calvin" no es "sin"
    return any(cola == inicio or cola.endswith(" " + inicio) for inicio in _INICIOS_NEGACION)


def _negado(texto: str, inicio: int, fin: int, interna: bool) -> bool:
    """Negación inmediatamente antes de la coincidencia (y, si aplica, dentro de ella)."""
    if _termina_en_negacion(texto[max(0, inicio - 40):inicio]):
        return True
    if not interna:
        return False
    coincidencia = texto[inicio:fin]
    palabras = list(_PALABRA.finditer(coincidencia))
    if not palabras:
        return False
    return _termina_en_negacion(coincidencia[:palabras[-1].start()])


def _contexto_producto(texto: str, inicio: int) -> bool:
    """True si lo que precede a la coincidencia es un producto o segmento, no un puesto."""
    return _PRODUCTO.search(texto[max(0, inicio - 30):inicio]) is not None


def _fragmento(texto: str, inicio: int, fin: int, margen: int = 30) -> str:
    return texto[max(0, inicio - margen): min(len(texto), fin + margen)].strip()


def _es_experiencia(texto: str, coincidencia: re.Match[str]) -> bool:
    """True si el número de años se refiere a experiencia, no a la edad."""
    anterior = texto[max(0, coincidencia.start() - 25):coincidencia.start()].lower()
    if "experiencia" in anterior:
        return True
    siguiente = texto[coincidencia.end():coincidencia.end() + 20].lower()
    return re.match(r"\s*,?\s*de\s+experiencia", siguiente) is not None


def _es_rango_de_experiencia(texto: str, coincidencia: re.Match[str]) -> bool:
    """Un rango de años que arranca por debajo de la mayoría de edad y sigue con contexto
    laboral ("entre 1 y 2 años en ventas") habla de experiencia, no de edad."""
    inferior = coincidencia.group(1)
    if not inferior or int(inferior) >= EDAD_MINIMA_LEGAL:
        return False
    siguiente = texto[coincidencia.end():coincidencia.end() + 20].lower()
    return re.match(r"\s*,?\s*(?:de\s+)?(?:experiencia|en\b)", siguiente) is not None


def _hallazgo_edad(texto: str) -> Hallazgo | None:
    for patron, tipo in _EDAD_COMPILADAS:
        for coincidencia in patron.finditer(texto):
            if _es_experiencia(texto, coincidencia):
                continue
            if tipo == "rango" and _es_rango_de_experiencia(texto, coincidencia):
                continue
            if tipo in ("minimo", "menor"):
                numero = coincidencia.group(1)
                if not numero or int(numero) <= EDAD_MINIMA_LEGAL:
                    continue   # mínimo de 18 o excluir a menores de edad: legal, no se marca
            return Hallazgo(regla="edad",
                            fragmento=_fragmento(texto, coincidencia.start(),
                                                 coincidencia.end()),
                            detalle=_DETALLE_EDAD, sugerencia=_SUGERENCIA_EDAD)
    return None


def detectar(texto: str | None) -> list[Hallazgo]:
    """Un hallazgo por regla que aparezca en el texto. Lista vacía = sin señales."""
    if not texto:
        return []
    hallazgos: list[Hallazgo] = []
    edad = _hallazgo_edad(texto)
    if edad is not None:
        hallazgos.append(edad)
    for regla, patrones in _COMPILADAS:
        hallazgo = _primera_coincidencia_valida(texto, regla, patrones)
        if hallazgo is not None:
            hallazgos.append(hallazgo)
    return hallazgos


def _primera_coincidencia_valida(texto: str, regla: Regla,
                                 patrones: tuple[re.Pattern[str], ...]) -> Hallazgo | None:
    """Revisa TODAS las coincidencias: una negada ("no se requiere foto") no debe ocultar
    un requisito real más adelante ("envíe su CV con foto")."""
    for patron in patrones:
        for coincidencia in patron.finditer(texto):
            if regla.negacion and _negado(texto, coincidencia.start(), coincidencia.end(),
                                          regla.negacion_interna):
                continue
            if regla.contexto_producto and _contexto_producto(texto, coincidencia.start()):
                continue
            if regla.predicado is not None and not regla.predicado(texto, coincidencia):
                continue
            return Hallazgo(
                regla=regla.nombre,
                fragmento=_fragmento(texto, coincidencia.start(), coincidencia.end()),
                detalle=regla.detalle,
                sugerencia=regla.sugerencia)
    return None


__all__ = ["EDAD_MINIMA_LEGAL", "Regla", "detectar"]
