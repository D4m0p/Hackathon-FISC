"""Las optimizaciones no cambian ningún resultado observable."""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from agentes.matching import (
    asignar, es_factible, incumplimientos, ranking_para_joven, tiene_alguna_factible,
)
from agentes.matching.puntaje import evaluar
from agentes.matching.solver import ESCALA, _publicadas

TIEMPO_MAXIMO_S = 10.0   # el de la versión original con CP-SAT
from contrato.modelos import Asignacion, Desglose, Infactible, ResultadoMatching
from ortools.sat.python import cp_model

from tests.test_propiedades import MERCADOS, jovenes, matrices, pesos_validos, vacantes

AJUSTES = settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])
AJUSTES_SOLVER = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@AJUSTES
@given(matriz=matrices(), j=jovenes("j"), v=vacantes("v"))
def test_es_factible_equivale_a_incumplimientos_vacio(matriz, j, v):
    assert es_factible(j, v, matriz) == (incumplimientos(j, v, matriz) == [])


@AJUSTES
@given(mercado=MERCADOS)
def test_tiene_alguna_factible_equivale_al_ranking(mercado):
    matriz, js, vs = mercado
    for j in js:
        assert tiene_alguna_factible(j, vs, matriz) == bool(ranking_para_joven(j, vs, matriz))


def _asignar_original(jovenes, vacantes, matriz, permitidos=None, pesos=None) -> ResultadoMatching:
    """Copia literal de `asignar` antes de optimizarla."""
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


@AJUSTES_SOLVER
@given(mercado=MERCADOS, pesos=st.one_of(st.none(), pesos_validos()))
def test_asignar_con_flujo_da_el_mismo_optimo_que_cp_sat(mercado, pesos):
    """El flujo de costo mínimo reemplazó a CP-SAT: mismo puntaje total, mismos infactibles y
    sin_asignar coherente. Ante empates puede elegir otra asignación igual de buena."""
    matriz, js, vs = mercado
    nuevo = asignar(js, vs, matriz, pesos=pesos)
    viejo = _asignar_original(js, vs, matriz, pesos=pesos)
    total = lambda r: sum(round(a.desglose.total * ESCALA) for a in r.asignaciones)  # noqa: E731
    assert total(nuevo) == total(viejo)
    assert nuevo.infactibles == viejo.infactibles
    asignados = {a.joven_id for a in nuevo.asignaciones}
    assert set(nuevo.sin_asignar) == {j.id for j in js} - asignados


@settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(matriz=matrices(), j=jovenes("j"), v=vacantes("v"), pesos=st.one_of(st.none(), pesos_validos()))
def test_total_rapido_igual_al_de_la_explicacion(matriz, j, v, pesos):
    """El solver usa `total` (solo el número); debe coincidir siempre con `puntaje().total`."""
    from agentes.matching.puntaje import puntaje, total
    if es_factible(j, v, matriz):
        assert total(j, v, matriz, pesos) == puntaje(j, v, matriz, pesos).total
