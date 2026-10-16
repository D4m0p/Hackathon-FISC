"""Agente de Matching: asignación óptima con cupos (OR-Tools CP-SAT).

Maximiza la suma de puntajes sujeta a:
- cada joven recibe como máximo una vacante;
- cada vacante recibe como máximo `cupos` jóvenes;
- solo pares factibles (traslado, presupuesto, horario, salario, habilidades
  obligatorias) y, si se indica, solo pares con interés mutuo (ambos dijeron sí).
"""
from __future__ import annotations

from ortools.sat.python import cp_model

from contrato.modelos import (
    Asignacion, Desglose, EstadoVacante, Infactible, Joven, Pesos, ResultadoMatching, Vacante,
)

from .puntaje import evaluar
from .traslados import MatrizTraslados

ESCALA = 10_000          # CP-SAT trabaja con enteros
TIEMPO_MAXIMO_S = 10.0


def _publicadas(vacantes: list[Vacante]) -> list[Vacante]:
    return [v for v in vacantes if v.estado == EstadoVacante.publicada]


def ranking_para_joven(joven: Joven, vacantes: list[Vacante], matriz: MatrizTraslados,
                       pesos: Pesos | None = None) -> list[tuple[Vacante, Desglose]]:
    """Tarjetas que ve un joven: solo vacantes factibles, de mejor a peor."""
    tarjetas = []
    for v in _publicadas(vacantes):
        r = evaluar(joven, v, matriz, pesos)
        if isinstance(r, Desglose):
            tarjetas.append((v, r))
    tarjetas.sort(key=lambda par: (-par[1].total, par[0].id))
    return tarjetas


def ranking_para_vacante(vacante: Vacante, jovenes: list[Joven], matriz: MatrizTraslados,
                         pesos: Pesos | None = None) -> list[tuple[Joven, Desglose]]:
    """Tarjetas que ve una empresa (el frontend las muestra anonimizadas)."""
    if vacante.estado != EstadoVacante.publicada:
        return []
    tarjetas = []
    for j in jovenes:
        r = evaluar(j, vacante, matriz, pesos)
        if isinstance(r, Desglose):
            tarjetas.append((j, r))
    tarjetas.sort(key=lambda par: (-par[1].total, par[0].id))
    return tarjetas


def asignar(jovenes: list[Joven], vacantes: list[Vacante], matriz: MatrizTraslados,
            permitidos: set[tuple[str, str]] | None = None, pesos: Pesos | None = None) -> ResultadoMatching:
    """`permitidos`: pares (joven_id, vacante_id) con interés mutuo. None = todos."""
    vacantes = _publicadas(vacantes)
    infactibles: list[Infactible] = []
    pares: dict[tuple[str, str], Desglose] = {}
    for j in sorted(jovenes, key=lambda x: x.id):
        for v in sorted(vacantes, key=lambda x: x.id):
            if permitidos is not None and (j.id, v.id) not in permitidos:
                continue
            r = evaluar(j, v, matriz, pesos)
            if isinstance(r, Infactible):
                infactibles.append(r)
            else:
                pares[(j.id, v.id)] = r

    modelo = cp_model.CpModel()
    x = {par: modelo.new_bool_var(f"x_{par[0]}_{par[1]}") for par in pares}
    for j in jovenes:
        modelo.add(sum(x[p] for p in x if p[0] == j.id) <= 1)
    for v in vacantes:
        modelo.add(sum(x[p] for p in x if p[1] == v.id) <= v.cupos)
    modelo.maximize(sum(round(pares[p].total * ESCALA) * x[p] for p in x))

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1        # resultado reproducible
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = TIEMPO_MAXIMO_S
    estado = solver.solve(modelo)
    if estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"El solver no encontró solución: {solver.status_name(estado)}")

    asignaciones = [Asignacion(joven_id=p[0], vacante_id=p[1], desglose=pares[p])
                    for p in sorted(x) if solver.value(x[p])]
    con_vacante = {a.joven_id for a in asignaciones}
    sin_asignar = sorted(j.id for j in jovenes if j.id not in con_vacante)
    return ResultadoMatching(asignaciones=asignaciones, sin_asignar=sin_asignar,
                             infactibles=infactibles)
