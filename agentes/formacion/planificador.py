"""Agente de Ruta de formación: plan de cursos óptimo (OR-Tools CP-SAT).

Para un joven sin vacante factible:
1. Vacantes alcanzables: aquellas cuyo ÚNICO impedimento es la falta de
   habilidades obligatorias (traslado, horario, presupuesto y salario ya sirven).
2. Para cada una, un modelo elige cursos que cubren la brecha, sujeto a:
   cupos disponibles, horario del joven, traslado al centro, presupuesto semanal
   de transporte y sin choques (los cursos van en paralelo: máximo uno por turno).
   Minimiza costo total (matrícula + transporte) + semanas valoradas en B/.5.
3. Se queda con el plan que cubre más brecha y, a igualdad, el más barato.
"""
from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from agentes.matching.puntaje import es_factible
from agentes.matching.traslados import MatrizTraslados
from contrato.modelos import (
    Curso, EstadoVacante, Joven, PlanFormacion, RequisitoHabilidad, Turno, Vacante,
)

VALOR_SEMANA = 5.0   # B/. con que se valora cada semana de duración
ESCALA = 100         # centavos
TIEMPO_MAXIMO_S = 10.0


@dataclass(frozen=True)
class _CursoViable:
    curso: Curso
    costo_total: float           # matrícula + transporte de todo el curso
    costo_semanal_transporte: float


def brecha(joven: Joven, vacante: Vacante) -> list[RequisitoHabilidad]:
    niveles: dict[str, int] = {}
    for h in joven.habilidades:
        niveles[h.codigo] = max(niveles.get(h.codigo, 0), h.nivel)
    return [r for r in vacante.habilidades_requeridas
            if r.obligatoria and niveles.get(r.codigo, 0) < r.nivel_minimo]


def vacantes_alcanzables(joven: Joven, vacantes: list[Vacante],
                         matriz: MatrizTraslados) -> list[tuple[Vacante, list[RequisitoHabilidad]]]:
    """Vacantes que solo fallan por habilidades: sin requisitos serían factibles."""
    alcanzables = []
    for v in sorted(vacantes, key=lambda x: x.id):
        if v.estado != EstadoVacante.publicada:
            continue
        falta = brecha(joven, v)
        if not falta:
            continue
        sin_requisitos = v.model_copy(update={"habilidades_requeridas": []})
        if es_factible(joven, sin_requisitos, matriz):
            alcanzables.append((v, falta))
    return alcanzables


def cursos_viables(joven: Joven, cursos: list[Curso], matriz: MatrizTraslados) -> tuple[list[_CursoViable], dict[str, str]]:
    """Cursos que el joven puede tomar, y el motivo de los descartados."""
    viables, descartados = [], {}
    for c in sorted(cursos, key=lambda x: x.id):
        viaje = matriz.viaje(joven.corregimiento, c.corregimiento)
        if c.cupos_disponibles <= 0:
            descartados[c.id] = "Sin cupos"
        elif not c.turnos <= joven.disponibilidad:
            descartados[c.id] = "El horario no coincide con su disponibilidad"
        elif viaje is None:
            descartados[c.id] = "Sin datos de traslado al centro"
        elif viaje.minutos > joven.max_minutos_traslado:
            descartados[c.id] = f"El traslado toma {viaje.minutos} min"
        else:
            semanal = round(viaje.costo * 2 * c.sesiones_por_semana, 2)
            total = round(c.costo + semanal * c.semanas, 2)
            viables.append(_CursoViable(c, total, semanal))
    return viables, descartados


def _otorga(curso: Curso, req: RequisitoHabilidad) -> bool:
    return any(h.codigo == req.codigo and h.nivel >= req.nivel_minimo
               for h in curso.habilidades_otorgadas)


def _resolver(joven: Joven, falta: list[RequisitoHabilidad],
              viables: list[_CursoViable]) -> tuple[list[_CursoViable], list[str]] | None:
    """Devuelve (cursos elegidos, códigos sin cubrir) o None si no hay solución."""
    cubribles = [r for r in falta if any(_otorga(cv.curso, r) for cv in viables)]
    sin_cubrir = sorted(r.codigo for r in falta if r not in cubribles)
    if not cubribles:
        return [], sin_cubrir

    modelo = cp_model.CpModel()
    x = [modelo.new_bool_var(f"c_{cv.curso.id}") for cv in viables]
    for r in cubribles:
        modelo.add(sum(x[i] for i, cv in enumerate(viables) if _otorga(cv.curso, r)) >= 1)
    for turno in Turno:
        modelo.add(sum(x[i] for i, cv in enumerate(viables) if turno in cv.curso.turnos) <= 1)
    # En paralelo, el transporte de todos los cursos se paga en la misma semana.
    modelo.add(sum(round(cv.costo_semanal_transporte * ESCALA) * x[i] for i, cv in enumerate(viables))
               <= round(joven.presupuesto_transporte_semanal * ESCALA))
    modelo.minimize(sum(round((cv.costo_total + VALOR_SEMANA * cv.curso.semanas) * ESCALA) * x[i]
                        for i, cv in enumerate(viables)))

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = TIEMPO_MAXIMO_S
    if solver.solve(modelo) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [cv for i, cv in enumerate(viables) if solver.value(x[i])], sin_cubrir


def planificar(joven: Joven, vacantes: list[Vacante], cursos: list[Curso],
               matriz: MatrizTraslados,
               alcanzables: list[tuple[Vacante, list[RequisitoHabilidad]]] | None = None) -> PlanFormacion:
    if alcanzables is None:
        alcanzables = vacantes_alcanzables(joven, vacantes, matriz)
    if not alcanzables:
        return PlanFormacion(
            joven_id=joven.id, vacantes_objetivo=[], cursos=[], habilidades_cubiertas=[],
            brecha_sin_cubrir=[], costo_total=0, semanas_total=0,
            motivos=["Ninguna vacante publicada le queda bien por traslado, horario, "
                     "presupuesto y salario; la formación sola no lo resolvería"])

    viables, descartados = cursos_viables(joven, cursos, matriz)
    mejor = None   # (clave de orden, vacante, falta, elegidos, sin_cubrir)
    for vacante, falta in alcanzables:
        r = _resolver(joven, falta, viables)
        if r is None:
            continue
        elegidos, sin_cubrir = r
        costo = sum(cv.costo_total for cv in elegidos)
        semanas = max((cv.curso.semanas for cv in elegidos), default=0)
        clave = (len(sin_cubrir), costo + VALOR_SEMANA * semanas, vacante.id)
        if mejor is None or clave < mejor[0]:
            mejor = (clave, vacante, falta, elegidos, sin_cubrir)

    if mejor is None:
        return PlanFormacion(
            joven_id=joven.id, vacantes_objetivo=[v.id for v, _ in alcanzables], cursos=[],
            habilidades_cubiertas=[], brecha_sin_cubrir=sorted({r.codigo for _, f in alcanzables for r in f}),
            costo_total=0, semanas_total=0,
            motivos=["Los cursos que cubren la brecha no caben juntos en su horario o presupuesto"])

    _, vacante, falta, elegidos, sin_cubrir = mejor
    ids = {cv.curso.id for cv in elegidos}
    cubiertas = sorted(r.codigo for r in falta if r.codigo not in sin_cubrir)

    # Otras vacantes alcanzables que este mismo plan también desbloquea.
    objetivo = [vacante.id]
    for v, f in alcanzables:
        if v.id != vacante.id and all(any(_otorga(cv.curso, r) for cv in elegidos) for r in f):
            objetivo.append(v.id)

    costo_total = round(sum(cv.costo_total for cv in elegidos), 2)
    semanas = max((cv.curso.semanas for cv in elegidos), default=0)
    motivos = [f"Cierra la brecha para «{vacante.titulo}»: {', '.join(cubiertas) or 'nada cubrible'}"]
    for cv in elegidos:
        motivos.append(f"{cv.curso.nombre} ({cv.curso.centro}): {cv.curso.semanas} semanas, "
                       f"B/.{cv.costo_total:.2f} con transporte")
    if sin_cubrir:
        motivos.append(f"Ningún curso disponible cubre: {', '.join(sin_cubrir)}")
    descartes_utiles = [f"{cid}: {m}" for cid, m in descartados.items()
                        if any(_otorga(c, r) for c in cursos if c.id == cid for r in falta)]
    if descartes_utiles:
        motivos.append("Cursos descartados que sí cubrían la brecha: " + "; ".join(descartes_utiles))

    return PlanFormacion(
        joven_id=joven.id, vacantes_objetivo=objetivo,
        cursos=[cv.curso.id for cv in sorted(elegidos, key=lambda cv: cv.curso.id)],
        habilidades_cubiertas=cubiertas, brecha_sin_cubrir=sin_cubrir,
        costo_total=costo_total, semanas_total=semanas, motivos=motivos)


def planificar_grupo(jovenes: list[Joven], vacantes: list[Vacante], cursos: list[Curso],
                     matriz: MatrizTraslados) -> list[PlanFormacion]:
    """Planes para varios jóvenes, descontando los cupos que va usando cada uno.

    Orden determinístico: primero quien tiene menos vacantes alcanzables (más
    necesidad), luego por id. Así un cupo escaso va a quien más lo necesita.
    """
    cupos = {c.id: c.cupos_disponibles for c in cursos}
    con_alcanzables = [(j, vacantes_alcanzables(j, vacantes, matriz)) for j in jovenes]
    orden = sorted(con_alcanzables, key=lambda par: (len(par[1]), par[0].id))
    planes = []
    for j, alcanzables in orden:
        disponibles = [c.model_copy(update={"cupos_disponibles": cupos[c.id]}) for c in cursos]
        plan = planificar(j, vacantes, disponibles, matriz, alcanzables)
        for cid in plan.cursos:
            cupos[cid] -= 1
        planes.append(plan)
    return planes


__all__ = ["brecha", "cursos_viables", "planificar", "planificar_grupo", "vacantes_alcanzables"]
