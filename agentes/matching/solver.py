"""Agente de Matching: asignación óptima con cupos (OR-Tools, flujo de costo mínimo).

Exacto y en tiempo polinomial (antes CP-SAT, que con miles de pares agotaba su límite
de tiempo sin solución). Maximiza la suma de puntajes sujeta a:
- cada joven recibe como máximo una vacante;
- cada vacante recibe como máximo `cupos` jóvenes;
- solo pares factibles (traslado, presupuesto, horario, salario, habilidades
  obligatorias) y, si se indica, solo pares con interés mutuo (ambos dijeron sí).
"""
from __future__ import annotations

from ortools.graph.python import min_cost_flow

from contrato.modelos import (
    Asignacion, Desglose, EstadoVacante, Infactible, Joven, Pesos, ResultadoMatching, Vacante,
)

from .puntaje import _niveles, es_factible, motivos_infactible, puntaje, total
from .traslados import MatrizTraslados

ESCALA = 10_000          # el flujo trabaja con costos enteros


def _publicadas(vacantes: list[Vacante]) -> list[Vacante]:
    return [v for v in vacantes if v.estado == EstadoVacante.publicada]


def ranking_para_joven(joven: Joven, vacantes: list[Vacante], matriz: MatrizTraslados,
                       pesos: Pesos | None = None) -> list[tuple[Vacante, Desglose]]:
    """Tarjetas que ve un joven: solo vacantes factibles, de mejor a peor."""
    tarjetas = []
    niveles = _niveles(joven)
    for v in _publicadas(vacantes):
        if es_factible(joven, v, matriz):   # las infactibles no se muestran: sin armar motivos
            tarjetas.append((v, puntaje(joven, v, matriz, pesos, niveles)))
    tarjetas.sort(key=lambda par: (-par[1].total, par[0].id))
    return tarjetas


def tiene_alguna_factible(joven: Joven, vacantes: list[Vacante], matriz: MatrizTraslados) -> bool:
    """Equivale a `bool(ranking_para_joven(...))`, cortando en la primera factible."""
    return any(es_factible(joven, v, matriz) for v in _publicadas(vacantes))


def ranking_para_vacante(vacante: Vacante, jovenes: list[Joven], matriz: MatrizTraslados,
                         pesos: Pesos | None = None) -> list[tuple[Joven, Desglose]]:
    """Tarjetas que ve una empresa (el frontend las muestra anonimizadas)."""
    if vacante.estado != EstadoVacante.publicada:
        return []
    tarjetas = []
    for j in jovenes:
        if es_factible(j, vacante, matriz):
            tarjetas.append((j, puntaje(j, vacante, matriz, pesos)))
    tarjetas.sort(key=lambda par: (-par[1].total, par[0].id))
    return tarjetas


def asignar(jovenes: list[Joven], vacantes: list[Vacante], matriz: MatrizTraslados,
            permitidos: set[tuple[str, str]] | None = None, pesos: Pesos | None = None) -> ResultadoMatching:
    """`permitidos`: pares (joven_id, vacante_id) con interés mutuo. None = todos."""
    vacantes = _publicadas(vacantes)
    infactibles: list[Infactible] = []
    totales: dict[tuple[str, str], float] = {}
    ordenadas = sorted(vacantes, key=lambda x: x.id)
    por_id_j = {j.id: j for j in jovenes}
    por_id_v = {v.id: v for v in ordenadas}
    niveles_de: dict[str, dict[str, int]] = {}
    for j in sorted(jovenes, key=lambda x: x.id):
        niveles = niveles_de[j.id] = _niveles(j)
        for v in ordenadas:
            if permitidos is not None and (j.id, v.id) not in permitidos:
                continue
            if es_factible(j, v, matriz):
                totales[(j.id, v.id)] = total(j, v, matriz, pesos, niveles)   # solo el número
            else:
                infactibles.append(Infactible(joven_id=j.id, vacante_id=v.id,
                                              motivos=motivos_infactible(j, v, matriz)))

    elegidos = _max_puntaje_con_cupos(totales, vacantes)
    # La explicación completa se arma solo para los pares elegidos.
    asignaciones = [Asignacion(joven_id=jid, vacante_id=vid,
                               desglose=puntaje(por_id_j[jid], por_id_v[vid], matriz, pesos, niveles_de[jid]))
                    for jid, vid in sorted(elegidos)]
    con_vacante = {a.joven_id for a in asignaciones}
    sin_asignar = sorted(j.id for j in jovenes if j.id not in con_vacante)
    return ResultadoMatching(asignaciones=asignaciones, sin_asignar=sin_asignar,
                             infactibles=infactibles)


def _max_puntaje_con_cupos(pares: dict[tuple[str, str], float], vacantes: list[Vacante]) -> set[tuple[str, str]]:
    """Asignación de puntaje total máximo como flujo de costo mínimo (exacto y polinomial).

    fuente → joven (cap. 1) → vacante (costo −puntaje) → sumidero (cap. = cupos), y además
    joven → sumidero (costo 0): quedarse sin vacante es válido. Sin ese atajo el flujo
    maximizaría la CANTIDAD de asignaciones en vez del puntaje total.
    Se construye siempre en el mismo orden, así el resultado es reproducible.
    """
    if not pares:
        return set()
    jovenes = sorted({j for j, _ in pares})
    ids_vacantes = sorted({v for _, v in pares})
    cupos = {v.id: v.cupos for v in vacantes}
    nodo_j = {j: 1 + i for i, j in enumerate(jovenes)}
    nodo_v = {v: 1 + len(jovenes) + i for i, v in enumerate(ids_vacantes)}
    fuente, sumidero = 0, 1 + len(jovenes) + len(ids_vacantes)

    flujo = min_cost_flow.SimpleMinCostFlow()
    for j in jovenes:
        flujo.add_arc_with_capacity_and_unit_cost(fuente, nodo_j[j], 1, 0)
        flujo.add_arc_with_capacity_and_unit_cost(nodo_j[j], sumidero, 1, 0)
    arcos: dict[int, tuple[str, str]] = {}
    for par in sorted(pares):
        arco = flujo.add_arc_with_capacity_and_unit_cost(
            nodo_j[par[0]], nodo_v[par[1]], 1, -round(pares[par] * ESCALA))
        arcos[arco] = par
    for v in ids_vacantes:
        flujo.add_arc_with_capacity_and_unit_cost(nodo_v[v], sumidero, cupos[v], 0)
    flujo.set_node_supply(fuente, len(jovenes))
    flujo.set_node_supply(sumidero, -len(jovenes))

    estado = flujo.solve()
    if estado != flujo.OPTIMAL:   # no debería pasar: el atajo hace factible cualquier caso
        raise RuntimeError(f"El flujo no encontró solución: {estado}")
    return {par for arco, par in arcos.items() if flujo.flow(arco) == 1}
