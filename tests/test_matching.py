import pytest

from agentes.matching import (
    MatrizTraslados, asignar, es_factible, evaluar, motivos_infactible, ranking_para_joven,
    ranking_para_vacante,
)
from contrato.modelos import (
    Desglose, EstadoVacante, HabilidadNivel, Infactible, Joven, RequisitoHabilidad,
    Traslado, Turno, Vacante,
)

MATRIZ = MatrizTraslados([
    Traslado(origen="la_chorrera", destino="tocumen", minutos=110, costo=2.50),
    Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.00),
    Traslado(origen="arraijan", destino="tocumen", minutos=80, costo=2.00),
    Traslado(origen="bella_vista", destino="tocumen", minutos=40, costo=1.00),
    Traslado(origen="bella_vista", destino="arraijan", minutos=45, costo=1.25),
])


def joven(id="j1", corregimiento="la_chorrera", habilidades=(), **cambios):
    datos = dict(id=id, corregimiento=corregimiento,
                 disponibilidad={Turno.manana, Turno.tarde},
                 presupuesto_transporte_semanal=20, salario_minimo=500,
                 habilidades=[HabilidadNivel(codigo=c, nivel=n) for c, n in habilidades])
    datos.update(cambios)
    return Joven(**datos)


def vacante(id="v1", corregimiento="arraijan", requisitos=(), **cambios):
    datos = dict(id=id, empresa_id="e1", titulo="Puesto", corregimiento=corregimiento,
                 turnos={Turno.manana}, salario_mensual=650, dias_por_semana=5,
                 estado=EstadoVacante.publicada,
                 habilidades_requeridas=[RequisitoHabilidad(codigo=c, nivel_minimo=n, obligatoria=o)
                                         for c, n, o in requisitos])
    datos.update(cambios)
    return Vacante(**datos)


# ---------- Matriz de traslados ----------

def test_traslado_se_busca_en_ambos_sentidos():
    assert MATRIZ.viaje("tocumen", "la_chorrera").minutos == 110


def test_mismo_corregimiento_tiene_valor_por_defecto():
    v = MATRIZ.viaje("tocumen", "tocumen")
    assert (v.minutos, v.costo) == (15, 0.0)


def test_un_corregimiento_valido_ausente_de_la_matriz_conserva_el_valor_por_defecto():
    # Un corregimiento real que no aparece en la tabla sigue recibiendo el supuesto de
    # viaje local (varios casos de `evals` dependen de esto: san_francisco fuera de la
    # matriz). La corrección de `san_miguelito` no debe tocar este comportamiento.
    v = MATRIZ.viaje("san_francisco", "san_francisco")
    assert (v.minutos, v.costo) == (15, 0.0)


def test_el_id_ambiguo_no_se_trata_como_mismo_corregimiento():
    # `san_miguelito` es un distrito, no un corregimiento: coincidir consigo mismo no es una
    # coincidencia geográfica confirmada. Debe caer en el mecanismo `sin_datos`, no en 15 min.
    assert MATRIZ.viaje("san_miguelito", "san_miguelito") is None


def test_par_en_ubicacion_ambigua_es_infactible_por_sin_datos():
    j = joven(corregimiento="san_miguelito")
    v = vacante(corregimiento="san_miguelito")
    assert not es_factible(j, v, MATRIZ)
    motivos = motivos_infactible(j, v, MATRIZ)
    assert any("No hay datos" in m for m in motivos)
    assert isinstance(evaluar(j, v, MATRIZ), Infactible)


# ---------- Factibilidad ----------

def test_par_factible_no_tiene_motivos():
    assert motivos_infactible(joven(), vacante(), MATRIZ) == []


def test_tocumen_es_infactible_desde_la_chorrera_por_tiempo():
    motivos = motivos_infactible(joven(), vacante(corregimiento="tocumen"), MATRIZ)
    assert any("110 min" in m for m in motivos)


def test_presupuesto_de_transporte_insuficiente():
    # 1.00 x 2 x 5 = 10.00 por semana
    motivos = motivos_infactible(joven(presupuesto_transporte_semanal=9.99), vacante(), MATRIZ)
    assert any("B/.10.00 por semana" in m for m in motivos)


def test_presupuesto_justo_alcanza():
    assert motivos_infactible(joven(presupuesto_transporte_semanal=10), vacante(), MATRIZ) == []


def test_turno_no_disponible():
    motivos = motivos_infactible(joven(disponibilidad={Turno.tarde}), vacante(), MATRIZ)
    assert any("manana" in m for m in motivos)


def test_salario_menor_al_minimo():
    motivos = motivos_infactible(joven(salario_minimo=700), vacante(), MATRIZ)
    assert any("menor que su mínimo" in m for m in motivos)


def test_falta_habilidad_obligatoria():
    v = vacante(requisitos=[("excel", 2, True)])
    assert any("excel" in m for m in motivos_infactible(joven(habilidades=[("excel", 1)]), v, MATRIZ))


def test_habilidad_opcional_no_bloquea():
    v = vacante(requisitos=[("excel", 2, False)])
    assert motivos_infactible(joven(), v, MATRIZ) == []


def test_sin_datos_de_traslado():
    motivos = motivos_infactible(joven(corregimiento="boquete"), vacante(), MATRIZ)
    assert any("No hay datos" in m for m in motivos)


def test_se_reportan_todos_los_motivos_a_la_vez():
    j = joven(disponibilidad={Turno.noche}, salario_minimo=900, presupuesto_transporte_semanal=0)
    assert len(motivos_infactible(j, vacante(corregimiento="tocumen"), MATRIZ)) == 4


# ---------- Puntaje ----------

def test_puntaje_desglosado_y_acotado():
    d = evaluar(joven(habilidades=[("caja", 1)]), vacante(requisitos=[("caja", 1, True)]), MATRIZ)
    assert isinstance(d, Desglose)
    assert d.habilidades == 1.0
    assert d.traslado == pytest.approx(1 - 30 / 75, abs=1e-4)
    assert 0 <= d.total <= 1
    assert any("Salario neto" in m for m in d.motivos)


def test_opcional_cumplida_sube_el_puntaje():
    reqs = [("caja", 1, True), ("ingles", 1, False)]
    sin = evaluar(joven(habilidades=[("caja", 1)]), vacante(requisitos=reqs), MATRIZ)
    con = evaluar(joven(habilidades=[("caja", 1), ("ingles", 2)]), vacante(requisitos=reqs), MATRIZ)
    assert con.total > sin.total
    assert sin.habilidades == pytest.approx(2 / 3, abs=1e-4)


def test_mas_cerca_puntua_mejor():
    lejos = evaluar(joven(corregimiento="bella_vista"), vacante(), MATRIZ)
    cerca = evaluar(joven(corregimiento="la_chorrera"), vacante(), MATRIZ)
    assert cerca.traslado > lejos.traslado


def test_evaluar_devuelve_infactible_con_motivos():
    r = evaluar(joven(), vacante(corregimiento="tocumen"), MATRIZ)
    assert isinstance(r, Infactible) and r.motivos


# ---------- Rankings para deslizar ----------

def test_ranking_del_joven_excluye_infactibles_y_borradores():
    vs = [vacante("v1"), vacante("v2", corregimiento="tocumen"),
          vacante("v3", estado=EstadoVacante.borrador),
          vacante("v4", corregimiento="la_chorrera")]
    ids = [v.id for v, _ in ranking_para_joven(joven(), vs, MATRIZ)]
    assert ids == ["v4", "v1"]   # la del mismo corregimiento primero


def test_ranking_de_la_vacante_ordena_por_puntaje():
    js = [joven("a", corregimiento="bella_vista"), joven("b", corregimiento="la_chorrera")]
    ids = [j.id for j, _ in ranking_para_vacante(vacante(), js, MATRIZ)]
    assert ids == ["b", "a"]


def test_vacante_bloqueada_no_recibe_candidatos():
    assert ranking_para_vacante(vacante(estado=EstadoVacante.bloqueada), [joven()], MATRIZ) == []


# ---------- Solver ----------

def test_respeta_los_cupos():
    js = [joven(f"j{i}") for i in range(5)]
    r = asignar(js, [vacante(cupos=2)], MATRIZ)
    assert len(r.asignaciones) == 2
    assert len(r.sin_asignar) == 3


def test_cada_joven_recibe_maximo_una_vacante():
    r = asignar([joven()], [vacante("v1"), vacante("v2")], MATRIZ)
    assert len(r.asignaciones) == 1


def test_nunca_asigna_pares_infactibles():
    r = asignar([joven()], [vacante(corregimiento="tocumen")], MATRIZ)
    assert r.asignaciones == [] and r.sin_asignar == ["j1"]
    assert r.infactibles[0].vacante_id == "v1"


def test_optimo_global_gana_al_voraz():
    # "a" puede ir a las dos vacantes y puntúa más en v1; "b" solo puede ir a v1.
    # El voraz daría v1 a "a" y dejaría a "b" sin nada. El óptimo coloca a los dos.
    a = joven("a", corregimiento="la_chorrera", habilidades=[("caja", 1), ("ventas", 1)])
    b = joven("b", corregimiento="la_chorrera", habilidades=[("caja", 1)])
    v1 = vacante("v1", corregimiento="la_chorrera", requisitos=[("caja", 1, True)])
    v2 = vacante("v2", corregimiento="arraijan", requisitos=[("ventas", 1, True)])
    r = asignar([a, b], [v1, v2], MATRIZ)
    pares = {(x.joven_id, x.vacante_id) for x in r.asignaciones}
    assert pares == {("a", "v2"), ("b", "v1")}


def test_solo_pares_con_interes_mutuo():
    r = asignar([joven("a"), joven("b")], [vacante()], MATRIZ, permitidos={("b", "v1")})
    assert [(x.joven_id, x.vacante_id) for x in r.asignaciones] == [("b", "v1")]


def test_resultado_reproducible():
    js = [joven(f"j{i}") for i in range(6)]
    vs = [vacante("v1", cupos=2), vacante("v2", corregimiento="la_chorrera", cupos=2)]
    primero = asignar(js, vs, MATRIZ).model_dump()
    for _ in range(3):
        assert asignar(js, vs, MATRIZ).model_dump() == primero


def test_sin_jovenes_ni_vacantes():
    r = asignar([], [], MATRIZ)
    assert r.asignaciones == [] and r.sin_asignar == []


def test_asignacion_queda_pendiente_del_orientador():
    r = asignar([joven()], [vacante()], MATRIZ)
    assert r.asignaciones[0].aprobada is None
