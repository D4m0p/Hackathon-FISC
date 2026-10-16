"""Entrevista corta (máx. 5 preguntas) para descubrir experiencia informal, y palabras
clave por habilidad para cuando no hay LLM. Cada pregunta solo puede otorgar sus
`codigos_posibles`: así una respuesta no puede inventar habilidades fuera de tema."""
from __future__ import annotations

from pydantic import BaseModel

MAX_PREGUNTAS = 5


class Pregunta(BaseModel):
    id: str
    texto: str
    ejemplo: str
    codigos_posibles: list[str]


PREGUNTAS: list[Pregunta] = [
    Pregunta(id="negocio", texto="¿Ha ayudado en un negocio familiar o ha vendido algo por su cuenta "
             "(comida, ropa, productos por redes sociales)?",
             ejemplo="Atiendo la tienda de mi tía los sábados y cobro en la caja.",
             codigos_posibles=["atencion_cliente", "manejo_caja", "ventas", "redes_sociales"]),
    Pregunta(id="comida", texto="¿Ha cocinado o servido comida para otras personas "
             "(fonda, eventos, ventas de comida)?",
             ejemplo="Ayudo a mi mamá a preparar y vender almuerzos.",
             codigos_posibles=["manipulacion_alimentos", "servicio_mesa", "atencion_cliente"]),
    Pregunta(id="tecnologia", texto="¿Ha ayudado a alguien con la computadora o el celular, "
             "o ha usado Excel u hojas de cálculo?",
             ejemplo="Le arreglo el celular a mis vecinos y llevo las cuentas en Excel.",
             codigos_posibles=["soporte_tecnico", "excel_basico", "redes_sociales"]),
    Pregunta(id="bodega", texto="¿Ha acomodado mercancía, cargado cajas u organizado un depósito o bodega?",
             ejemplo="Ayudé a ordenar el depósito de un minisúper en diciembre.",
             codigos_posibles=["reposicion_inventario", "logistica_bodega"]),
    Pregunta(id="ingles", texto="¿Habla algo de inglés? ¿Dónde lo ha practicado?",
             ejemplo="Lo practico con turistas en el Casco Antiguo.",
             codigos_posibles=["ingles_conversacional"]),
]

# Raíces normalizadas (sin tildes, minúsculas) que delatan cada habilidad.
PALABRAS_CLAVE: dict[str, list[str]] = {
    "atencion_cliente": ["atiend", "atencion al cliente", "atender", "clientes", "servicio al cliente"],
    "manejo_caja": ["caja", "cobr", "cajer", "vuelto", "efectivo"],
    "ventas": ["vend", "venta", "vendedor"],
    "excel_basico": ["excel", "hoja de calculo", "hojas de calculo"],
    "ingles_conversacional": ["ingles", "english", "turistas"],
    "reposicion_inventario": ["reponer", "reposicion", "inventario", "acomod", "mercancia", "perchas"],
    "manipulacion_alimentos": ["cocin", "comida", "alimentos", "almuerzo", "carnet de salud", "fonda"],
    "soporte_tecnico": ["arregl", "repar", "computadora", "soporte", "formate", "instal"],
    "redes_sociales": ["redes sociales", "instagram", "facebook", "tiktok", "whatsapp"],
    "logistica_bodega": ["bodega", "deposito", "cargar", "carga", "despacho", "almacen"],
    "servicio_mesa": ["mesero", "mesera", "servir", "mesas", "salonero"],
}


def preguntas_para(codigos_taxonomia: set[str]) -> list[Pregunta]:
    """Las preguntas que todavía tienen sentido con la taxonomía actual."""
    salida = []
    for p in PREGUNTAS:
        posibles = [c for c in p.codigos_posibles if c in codigos_taxonomia]
        if posibles:
            salida.append(p.model_copy(update={"codigos_posibles": posibles}))
    return salida[:MAX_PREGUNTAS]
