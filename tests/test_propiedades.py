"""Pruebas con casos aleatorios (Hypothesis): propiedades que deben cumplirse SIEMPRE.

Para el Matching y la Ruta de formación, en instancias pequeñas se compara el solver
contra una búsqueda exhaustiva de todas las combinaciones: si existe una solución mejor
que la del solver, la prueba falla.
"""
from __future__ import annotations

import itertools

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from agentes.formacion import casi_califica, cursos_viables, planificar_grupo
from agentes.formacion.planificador import ESCALA as ESCALA_F
from agentes.formacion.planificador import VALOR_SEMANA, _otorga, _resolver, brecha
from agentes.matching import MatrizTraslados, asignar, evaluar, incumplimientos, motivos_infactible
from agentes.matching.solver import ESCALA as ESCALA_M
from contrato.modelos import (
    Curso, Desglose, EstadoVacante, HabilidadNivel, Joven, Pesos, RequisitoHabilidad, TipoIncumplimiento,
    Traslado, Turno, Vacante,
)

LUGARES = ["a", "b", "c", "d"]
HABILIDADES = ["caja", "ventas", "excel", "ingles", "bodega"]
TURNOS = [Turno.manana, Turno.tarde, Turno.noche]

AJUSTES = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])


# ---------- generadores ----------

@st.composite
def matrices(draw) -> MatrizTraslados:
    viajes = []
    for o, d in itertools.combinations(LUGARES, 2):
        viajes.append(Traslado(origen=o, destino=d, minutos=draw(st.integers(5, 100)),
                               costo=draw(st.sampled_from([0.25, 0.35, 0.5, 1.0, 1.5, 2.0]))))
    return MatrizTraslados(viajes)


def habilidades_nivel(max_size=4):
    return st.lists(st.builds(HabilidadNivel, codigo=st.sampled_from(HABILIDADES),
                              nivel=st.integers(1, 3)), max_size=max_size)


def jovenes(id_):
    return st.builds(
        Joven, id=st.just(id_), corregimiento=st.sampled_from(LUGARES),
        disponibilidad=st.sets(st.sampled_from(TURNOS), min_size=1),
        presupuesto_transporte_semanal=st.sampled_from([0, 5, 10, 15, 20, 30, 50]),
        salario_minimo=st.sampled_from([0, 0, 500, 600, 700]),
        max_minutos_traslado=st.sampled_from([30, 60, 75, 90, 120]),
        habilidades=habilidades_nivel())


def vacantes(id_):
    return st.builds(
        Vacante, id=st.just(id_), empresa_id=st.just("e"), titulo=st.just(f"Puesto {id_}"),
        corregimiento=st.sampled_from(LUGARES),
        turnos=st.sets(st.sampled_from(TURNOS), min_size=1, max_size=2),
        dias_por_semana=st.integers(1, 6), salario_mensual=st.sampled_from([450, 600, 650, 800]),
        cupos=st.integers(1, 2), estado=st.just(EstadoVacante.publicada),
        habilidades_requeridas=st.lists(st.builds(
            RequisitoHabilidad, codigo=st.sampled_from(HABILIDADES), nivel_minimo=st.integers(1, 3),
            obligatoria=st.booleans()), max_size=3, unique_by=lambda r: r.codigo))


def cursos(id_):
    return st.builds(
        Curso, id=st.just(id_), centro=st.just("INADEH"), nombre=st.just(f"Curso {id_}"),
        corregimiento=st.sampled_from(LUGARES),
        turnos=st.sets(st.sampled_from(TURNOS), min_size=1, max_size=2),
        sesiones_por_semana=st.integers(1, 5), semanas=st.integers(1, 12),
        costo=st.sampled_from([0, 0, 10, 25]), cupos_disponibles=st.integers(0, 3),
        habilidades_otorgadas=st.lists(st.builds(HabilidadNivel, codigo=st.sampled_from(HABILIDADES),
                                                 nivel=st.integers(1, 3)), min_size=1, max_size=2))


@st.composite
def mercados(draw, max_j=4, max_v=3):
    nj = draw(st.integers(0, max_j))
    nv = draw(st.integers(0, max_v))
    js = [draw(jovenes(f"j{i}")) for i in range(nj)]
    vs = [draw(vacantes(f"v{i}")) for i in range(nv)]
    return draw(matrices()), js, vs


@st.composite
def mercados_competidos(draw):
    """Muchos pares factibles y pocos cupos: jóvenes compitiendo por las mismas vacantes."""
    matriz = draw(matrices())
    nj, nv = draw(st.integers(2, 5)), draw(st.integers(1, 3))
    js = [draw(jovenes(f"j{i}")).model_copy(update={
        "disponibilidad": {Turno.manana, Turno.tarde}, "presupuesto_transporte_semanal": 50,
        "max_minutos_traslado": 120, "salario_minimo": 0}) for i in range(nj)]
    vs = [draw(vacantes(f"v{i}")).model_copy(update={
        "turnos": {Turno.manana}, "cupos": draw(st.integers(1, 2)),
        "habilidades_requeridas": [RequisitoHabilidad(codigo=c, obligatoria=False) for c in
                                   draw(st.lists(st.sampled_from(HABILIDADES), max_size=3, unique=True))]})
          for i in range(nv)]
    return matriz, js, vs


MERCADOS = st.one_of(mercados(), mercados_competidos())


# ---------- Matching ----------

@st.composite
def pesos_validos(draw) -> Pesos:
    h = draw(st.integers(5, 80))
    t = draw(st.integers(max(5, 20 - h), min(80, 95 - h)))
    return Pesos(habilidades=h / 100, traslado=t / 100, salario=(100 - h - t) / 100)


def _mejor_exhaustivo(js, vs, matriz, permitidos=None, pesos=None) -> int:
    opciones = []
    for j in js:
        posibles = [None]
        for v in vs:
            if permitidos is not None and (j.id, v.id) not in permitidos:
                continue
            r = evaluar(j, v, matriz, pesos)
            if isinstance(r, Desglose):
                posibles.append((v.id, round(r.total * ESCALA_M)))
        opciones.append(posibles)
    cupos = {v.id: v.cupos for v in vs}
    mejor = 0
    for combo in itertools.product(*opciones):
        usados: dict[str, int] = {}
        for x in combo:
            if x:
                usados[x[0]] = usados.get(x[0], 0) + 1
        if all(n <= cupos[v] for v, n in usados.items()):
            mejor = max(mejor, sum(x[1] for x in combo if x))
    return mejor


@AJUSTES
@given(MERCADOS)
def test_matching_respeta_todas_las_restricciones(m):
    matriz, js, vs = m
    r = asignar(js, vs, matriz)
    por_id_j, por_id_v = {j.id: j for j in js}, {v.id: v for v in vs}
    for a in r.asignaciones:
        assert motivos_infactible(por_id_j[a.joven_id], por_id_v[a.vacante_id], matriz) == []
    assert len({a.joven_id for a in r.asignaciones}) == len(r.asignaciones)
    for v in vs:
        assert sum(1 for a in r.asignaciones if a.vacante_id == v.id) <= v.cupos
    assert sorted({a.joven_id for a in r.asignaciones} | set(r.sin_asignar)) == sorted(por_id_j)


@AJUSTES
@given(MERCADOS)
def test_matching_es_optimo_frente_a_busqueda_exhaustiva(m):
    matriz, js, vs = m
    r = asignar(js, vs, matriz)
    obtenido = sum(round(a.desglose.total * ESCALA_M) for a in r.asignaciones)
    assert obtenido == _mejor_exhaustivo(js, vs, matriz)


@AJUSTES
@given(MERCADOS, pesos_validos())
def test_matching_es_optimo_con_cualquier_combinacion_valida_de_pesos(m, pesos):
    matriz, js, vs = m
    r = asignar(js, vs, matriz, pesos=pesos)
    obtenido = sum(round(a.desglose.total * ESCALA_M) for a in r.asignaciones)
    assert obtenido == _mejor_exhaustivo(js, vs, matriz, pesos=pesos)
    assert all(a.desglose.pesos == pesos for a in r.asignaciones)


@AJUSTES
@given(MERCADOS, st.data())
def test_matching_con_interes_mutuo_solo_usa_pares_permitidos_y_sigue_siendo_optimo(m, data):
    matriz, js, vs = m
    todos = [(j.id, v.id) for j in js for v in vs]
    permitidos = set(data.draw(st.lists(st.sampled_from(todos), unique=True)) if todos else [])
    r = asignar(js, vs, matriz, permitidos=permitidos)
    assert all((a.joven_id, a.vacante_id) in permitidos for a in r.asignaciones)
    obtenido = sum(round(a.desglose.total * ESCALA_M) for a in r.asignaciones)
    assert obtenido == _mejor_exhaustivo(js, vs, matriz, permitidos)


@AJUSTES
@given(MERCADOS)
def test_el_orden_de_entrada_no_cambia_el_valor_optimo(m):
    matriz, js, vs = m
    a = asignar(js, vs, matriz)
    b = asignar(list(reversed(js)), list(reversed(vs)), matriz)
    total = lambda r: sum(round(x.desglose.total * ESCALA_M) for x in r.asignaciones)  # noqa: E731
    assert total(a) == total(b)


# ---------- Puntaje ----------

@AJUSTES
@given(matrices(), jovenes("j"), vacantes("v"))
def test_componentes_del_puntaje_entre_0_y_1(matriz, j, v):
    r = evaluar(j, v, matriz)
    if isinstance(r, Desglose):
        for x in (r.habilidades, r.traslado, r.salario, r.total):
            assert 0 <= x <= 1


@AJUSTES
@given(matrices(), jovenes("j"), vacantes("v"), st.sampled_from(LUGARES))
def test_el_corregimiento_nunca_mueve_el_componente_de_habilidades(matriz, j, v, otro):
    """Base de la auditoría contrafactual: mudarse solo puede cambiar traslado y salario."""
    a = evaluar(j, v, matriz)
    b = evaluar(j.model_copy(update={"corregimiento": otro}), v, matriz)
    if isinstance(a, Desglose) and isinstance(b, Desglose):
        assert a.habilidades == b.habilidades


@AJUSTES
@given(matrices(), jovenes("j"), vacantes("v"), st.sampled_from(HABILIDADES), st.integers(1, 3))
def test_aprender_algo_nunca_empeora(matriz, j, v, codigo, nivel):
    antes = evaluar(j, v, matriz)
    despues = evaluar(j.model_copy(update={"habilidades": j.habilidades + [HabilidadNivel(codigo=codigo, nivel=nivel)]}),
                      v, matriz)
    if isinstance(antes, Desglose):
        assert isinstance(despues, Desglose) and despues.total >= antes.total


@AJUSTES
@given(matrices(), jovenes("j"), vacantes("v"), st.sampled_from([1, 5, 20]))
def test_mas_presupuesto_nunca_vuelve_infactible_un_par(matriz, j, v, extra):
    if not incumplimientos(j, v, matriz):
        mas = j.model_copy(update={"presupuesto_transporte_semanal": j.presupuesto_transporte_semanal + extra})
        assert not incumplimientos(mas, v, matriz)


# ---------- Ruta de formación ----------

def _mejor_plan_exhaustivo(joven, falta, viables):
    cubribles = [r for r in falta if any(_otorga(cv.curso, r) for cv in viables)]
    mejor = None
    for k in range(len(viables) + 1):
        for combo in itertools.combinations(viables, k):
            turnos = [t for cv in combo for t in cv.curso.turnos]
            if len(turnos) != len(set(turnos)):
                continue
            transporte = sum(round(cv.costo_semanal_transporte * ESCALA_F) for cv in combo)
            if transporte > round(joven.presupuesto_transporte_semanal * ESCALA_F):
                continue
            if not all(any(_otorga(cv.curso, r) for cv in combo) for r in cubribles):
                continue
            valor = sum(round((cv.costo_total + VALOR_SEMANA * cv.curso.semanas) * ESCALA_F) for cv in combo)
            mejor = valor if mejor is None else min(mejor, valor)
    return mejor


@st.composite
def escenarios_formacion(draw):
    matriz = draw(matrices())
    j = draw(jovenes("j"))
    v = draw(vacantes("v"))
    cs = [draw(cursos(f"c{i}")) for i in range(draw(st.integers(0, 6)))]
    return matriz, j, v, cs


@st.composite
def escenarios_formacion_ricos(draw):
    """Casos donde la Ruta de formación tiene que ELEGIR: el joven tiene una brecha real
    y hay varios cursos (que compiten por turnos y presupuesto) que la cubren."""
    matriz = draw(matrices())
    requeridas = draw(st.lists(st.sampled_from(HABILIDADES), min_size=1, max_size=3, unique=True))
    v = draw(vacantes("v")).model_copy(update={"habilidades_requeridas": [
        RequisitoHabilidad(codigo=c, nivel_minimo=draw(st.integers(1, 2))) for c in requeridas]})
    j = draw(jovenes("j")).model_copy(update={
        "habilidades": [], "max_minutos_traslado": 120,
        "disponibilidad": set(draw(st.sets(st.sampled_from(TURNOS), min_size=2))),
        "presupuesto_transporte_semanal": draw(st.sampled_from([5, 10, 20, 40]))})
    cs = []
    for i in range(draw(st.integers(2, 7))):
        c = draw(cursos(f"c{i}"))
        otorga = [HabilidadNivel(codigo=draw(st.sampled_from(requeridas)), nivel=draw(st.integers(1, 3)))
                  for _ in range(draw(st.integers(1, 2)))]
        cs.append(c.model_copy(update={
            "habilidades_otorgadas": otorga, "cupos_disponibles": draw(st.integers(0, 3)) or 1,
            "turnos": {draw(st.sampled_from(sorted(j.disponibilidad, key=lambda t: t.value)))}}))
    return matriz, j, v, cs


@AJUSTES
@given(st.one_of(escenarios_formacion(), escenarios_formacion_ricos()))
def test_ruta_de_formacion_es_optima_y_respeta_restricciones(e):
    matriz, j, v, cs = e
    falta = brecha(j, v)
    viables, _ = cursos_viables(j, cs, matriz)
    r = _resolver(j, falta, viables)
    esperado = _mejor_plan_exhaustivo(j, falta, viables)
    if r is None:
        assert esperado is None
        return
    elegidos, sin_cubrir = r
    turnos = [t for cv in elegidos for t in cv.curso.turnos]
    assert len(turnos) == len(set(turnos))                                  # sin choques
    assert sum(cv.costo_semanal_transporte for cv in elegidos) <= j.presupuesto_transporte_semanal + 1e-9
    for cv in elegidos:                                                     # todos viables
        assert cv.curso.cupos_disponibles > 0 and cv.curso.turnos <= j.disponibilidad
    for req in falta:                                                       # cubre todo lo cubrible
        assert (req.codigo in sin_cubrir) != any(_otorga(cv.curso, req) for cv in elegidos)
    valor = sum(round((cv.costo_total + VALOR_SEMANA * cv.curso.semanas) * ESCALA_F) for cv in elegidos)
    assert valor == esperado


@AJUSTES
@given(matrices(), st.lists(st.integers(0, 3), min_size=1, max_size=5).flatmap(
    lambda ns: st.tuples(*[jovenes(f"j{i}") for i in range(len(ns))])),
    st.lists(st.integers(0, 1), min_size=1, max_size=3).flatmap(
    lambda ns: st.tuples(*[vacantes(f"v{i}") for i in range(len(ns))])),
    st.lists(st.integers(0, 1), min_size=1, max_size=4).flatmap(
    lambda ns: st.tuples(*[cursos(f"c{i}") for i in range(len(ns))])))
def test_planes_de_grupo_nunca_exceden_los_cupos_de_un_curso(matriz, js, vs, cs):
    planes = planificar_grupo(list(js), list(vs), list(cs), matriz)
    for c in cs:
        assert sum(1 for p in planes if c.id in p.cursos) <= c.cupos_disponibles


# ---------- Casi califica ----------

@AJUSTES
@given(escenarios_formacion())
def test_casi_califica_siempre_es_una_sola_falla_y_sus_cursos_sirven(e):
    matriz, j, v, cs = e
    for c in casi_califica(j, [v], cs, matriz):
        assert len(incumplimientos(j, v, matriz)) == 1
        assert c.incumplimiento.tipo != TipoIncumplimiento.sin_datos
        viables = {cv.curso.id for cv in cursos_viables(j, cs, matriz)[0]}
        for cid in c.cursos:
            curso = next(x for x in cs if x.id == cid)
            assert cid in viables
            assert any(h.codigo == c.incumplimiento.codigo for h in curso.habilidades_otorgadas)
