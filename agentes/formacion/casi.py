"""Vacantes a las que al joven le falta UNA sola cosa, y qué puede hacer al respecto.

Todo es determinístico: usa las mismas restricciones del Matching y, si lo que falta
es una habilidad, busca cursos que el joven realmente pueda tomar (horario, cupos,
traslado y presupuesto).
"""
from __future__ import annotations

from agentes.matching import MatrizTraslados, incumplimientos
from contrato.modelos import (
    CasiCalifica, Curso, EstadoVacante, Incumplimiento, Joven, TipoIncumplimiento, Vacante,
)

from .planificador import cursos_viables

# Lo accionable primero: una habilidad que un curso cubre; al final, una habilidad
# que ningún curso disponible cubre (la más difícil de resolver).
ORDEN = {TipoIncumplimiento.presupuesto: 1, TipoIncumplimiento.traslado: 2,
         TipoIncumplimiento.horario: 3, TipoIncumplimiento.salario: 4}


def _prioridad(c: CasiCalifica) -> int:
    if c.incumplimiento.tipo == TipoIncumplimiento.habilidad:
        return 0 if c.cursos else 5
    return ORDEN[c.incumplimiento.tipo]


def _cursos_para(joven: Joven, codigo: str, nivel: int, cursos: list[Curso],
                 matriz: MatrizTraslados) -> list[Curso]:
    viables, _ = cursos_viables(joven, cursos, matriz)
    return [cv.curso for cv in viables
            if cv.costo_semanal_transporte <= joven.presupuesto_transporte_semanal
            and any(h.codigo == codigo and h.nivel >= nivel for h in cv.curso.habilidades_otorgadas)]


def _sugerencia(joven: Joven, vacante: Vacante, falla: Incumplimiento, cursos: list[Curso],
                matriz: MatrizTraslados, nombres: dict[str, str]) -> tuple[str, list[str]]:
    t = falla.tipo
    if t == TipoIncumplimiento.habilidad:
        nombre = nombres.get(falla.codigo, falla.codigo)
        nivel = next(r.nivel_minimo for r in vacante.habilidades_requeridas if r.codigo == falla.codigo)
        opciones = sorted(_cursos_para(joven, falla.codigo, nivel, cursos, matriz),
                          key=lambda c: (c.semanas, c.costo, c.id))
        if not opciones:
            return f"Le falta {nombre}; por ahora ningún curso disponible le queda bien.", []
        c = opciones[0]
        return (f"Le falta {nombre}. El curso «{c.nombre}» ({c.centro}) la cubre en "
                f"{c.semanas} semanas y cabe en su horario y presupuesto.", [x.id for x in opciones])
    if t == TipoIncumplimiento.presupuesto:
        return f"Le faltan B/.{falla.faltante:.2f} por semana para el pasaje.", []
    if t == TipoIncumplimiento.traslado:
        minutos = joven.max_minutos_traslado + int(falla.faltante)
        return (f"Queda a {falla.faltante:.0f} min más de lo que usted acepta; "
                f"si amplía su límite a {minutos} min, calificaría."), []
    if t == TipoIncumplimiento.horario:
        return f"Si pudiera trabajar en el turno {falla.codigo}, calificaría.", []
    return f"Paga B/.{falla.faltante:.2f} menos que su mínimo; si lo ajusta, calificaría.", []


def casi_califica(joven: Joven, vacantes: list[Vacante], cursos: list[Curso],
                  matriz: MatrizTraslados, nombres: dict[str, str] | None = None) -> list[CasiCalifica]:
    """`nombres`: código de habilidad → nombre legible (si falta, se muestra el código)."""
    resultado = []
    for v in vacantes:
        if v.estado != EstadoVacante.publicada:
            continue
        fallas = incumplimientos(joven, v, matriz)
        if len(fallas) != 1 or fallas[0].tipo == TipoIncumplimiento.sin_datos:
            continue
        sugerencia, ids = _sugerencia(joven, v, fallas[0], cursos, matriz, nombres or {})
        resultado.append(CasiCalifica(vacante_id=v.id, titulo=v.titulo, incumplimiento=fallas[0],
                                      sugerencia=sugerencia, cursos=ids))
    resultado.sort(key=lambda c: (_prioridad(c), c.incumplimiento.faltante or 0, c.vacante_id))
    return resultado
