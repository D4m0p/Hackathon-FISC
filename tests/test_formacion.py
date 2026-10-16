from agentes.formacion import planificar, planificar_grupo, vacantes_alcanzables
from agentes.matching import MatrizTraslados
from contrato.modelos import (
    Curso, EstadoVacante, HabilidadNivel, Joven, RequisitoHabilidad, Traslado, Turno, Vacante,
)

MATRIZ = MatrizTraslados([
    Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.00),
    Traslado(origen="la_chorrera", destino="tocumen", minutos=110, costo=2.50),
    Traslado(origen="la_chorrera", destino="bella_vista", minutos=70, costo=1.50),
])


def joven(id="j1", habilidades=(), **cambios):
    datos = dict(id=id, corregimiento="la_chorrera",
                 disponibilidad={Turno.manana, Turno.tarde},
                 presupuesto_transporte_semanal=20, salario_minimo=500,
                 habilidades=[HabilidadNivel(codigo=c, nivel=n) for c, n in habilidades])
    datos.update(cambios)
    return Joven(**datos)


def vacante(id="v1", requisitos=(("excel", 1),), **cambios):
    datos = dict(id=id, empresa_id="e1", titulo=f"Puesto {id}", corregimiento="arraijan",
                 turnos={Turno.manana}, salario_mensual=650, estado=EstadoVacante.publicada,
                 habilidades_requeridas=[RequisitoHabilidad(codigo=c, nivel_minimo=n)
                                         for c, n in requisitos])
    datos.update(cambios)
    return Vacante(**datos)


def curso(id, otorga=(("excel", 1),), costo=0, turnos=(Turno.manana,), semanas=4,
          corregimiento="la_chorrera", cupos=10, sesiones=2):
    return Curso(id=id, centro="INADEH", nombre=f"Curso {id}", corregimiento=corregimiento,
                 turnos=set(turnos), sesiones_por_semana=sesiones, semanas=semanas, costo=costo,
                 cupos_disponibles=cupos,
                 habilidades_otorgadas=[HabilidadNivel(codigo=c, nivel=n) for c, n in otorga])


# ---------- Vacantes alcanzables ----------

def test_solo_cuentan_vacantes_que_fallan_unicamente_por_habilidades():
    vs = [vacante("v1"), vacante("v2", corregimiento="tocumen"),
          vacante("v3", requisitos=())]                       # v3 ya es factible
    assert [v.id for v, _ in vacantes_alcanzables(joven(), vs, MATRIZ)] == ["v1"]


def test_borrador_no_es_alcanzable():
    assert vacantes_alcanzables(joven(), [vacante(estado=EstadoVacante.borrador)], MATRIZ) == []


def test_sin_vacantes_alcanzables_el_plan_lo_explica():
    plan = planificar(joven(), [vacante(corregimiento="tocumen")], [curso("c1")], MATRIZ)
    assert plan.cursos == [] and "formación sola no lo resolvería" in plan.motivos[0]


# ---------- Elección de cursos ----------

def test_elige_el_curso_mas_barato_que_cubre_la_brecha():
    plan = planificar(joven(), [vacante()], [curso("caro", costo=80), curso("barato", costo=0)], MATRIZ)
    assert plan.cursos == ["barato"]
    assert plan.habilidades_cubiertas == ["excel"] and plan.brecha_sin_cubrir == []


def test_el_costo_incluye_transporte_al_centro():
    # Centro en Arraiján: 1.00 x 2 viajes x 2 sesiones x 4 semanas = 16.00
    plan = planificar(joven(), [vacante()], [curso("c1", corregimiento="arraijan")], MATRIZ)
    assert plan.costo_total == 16.00


def test_un_curso_cercano_gratis_gana_a_uno_lejano_gratis():
    cs = [curso("lejos", corregimiento="bella_vista"), curso("cerca")]
    assert planificar(joven(), [vacante()], cs, MATRIZ).cursos == ["cerca"]


def test_nivel_insuficiente_no_cubre():
    v = vacante(requisitos=(("excel", 2),))
    plan = planificar(joven(), [v], [curso("basico", otorga=(("excel", 1),))], MATRIZ)
    assert plan.cursos == [] and plan.brecha_sin_cubrir == ["excel"]


def test_curso_sin_cupos_se_descarta_y_se_explica():
    plan = planificar(joven(), [vacante()], [curso("lleno", cupos=0)], MATRIZ)
    assert plan.cursos == []
    assert any("lleno: Sin cupos" in m for m in plan.motivos)


def test_curso_fuera_de_su_horario_se_descarta():
    plan = planificar(joven(), [vacante()], [curso("noche", turnos=(Turno.noche,))], MATRIZ)
    assert plan.cursos == []


def test_curso_demasiado_lejos_se_descarta():
    plan = planificar(joven(), [vacante()], [curso("lejos", corregimiento="tocumen")], MATRIZ)
    assert plan.cursos == []


def test_no_elige_dos_cursos_en_el_mismo_turno():
    v = vacante(requisitos=(("excel", 1), ("ingles", 1)))
    cs = [curso("excel_m", otorga=(("excel", 1),), turnos=(Turno.manana,)),
          curso("ingles_m", otorga=(("ingles", 1),), turnos=(Turno.manana,)),
          curso("ingles_t", otorga=(("ingles", 1),), turnos=(Turno.tarde,), costo=30)]
    plan = planificar(joven(), [v], cs, MATRIZ)
    assert plan.cursos == ["excel_m", "ingles_t"]


def test_respeta_el_presupuesto_semanal_de_transporte():
    # Dos cursos en Bella Vista: 1.50 x 2 x 2 = 6.00 por semana cada uno.
    v = vacante(requisitos=(("excel", 1), ("ingles", 1)))
    cs = [curso("a", otorga=(("excel", 1),), corregimiento="bella_vista"),
          curso("b", otorga=(("ingles", 1),), turnos=(Turno.tarde,), corregimiento="bella_vista")]
    assert planificar(joven(presupuesto_transporte_semanal=12), [v], cs, MATRIZ).cursos == ["a", "b"]
    plan = planificar(joven(presupuesto_transporte_semanal=11.99), [v], cs, MATRIZ)
    assert plan.cursos == [] and "no caben juntos" in plan.motivos[0]


def test_habilidad_que_nadie_ensena_queda_como_brecha():
    v = vacante(requisitos=(("excel", 1), ("soldadura", 1)))
    plan = planificar(joven(), [v], [curso("c1")], MATRIZ)
    assert plan.cursos == ["c1"] and plan.brecha_sin_cubrir == ["soldadura"]


def test_prefiere_la_vacante_que_se_cubre_completa():
    parcial = vacante("v1", requisitos=(("excel", 1), ("soldadura", 1)))
    completa = vacante("v2", requisitos=(("ingles", 1),))
    cs = [curso("c_excel"), curso("c_ingles", otorga=(("ingles", 1),), costo=50)]
    plan = planificar(joven(), [parcial, completa], cs, MATRIZ)
    assert plan.vacantes_objetivo[0] == "v2" and plan.brecha_sin_cubrir == []


def test_el_plan_lista_otras_vacantes_que_tambien_desbloquea():
    plan = planificar(joven(), [vacante("v1"), vacante("v2")], [curso("c1")], MATRIZ)
    assert plan.vacantes_objetivo == ["v1", "v2"]


def test_semanas_son_las_del_curso_mas_largo_porque_van_en_paralelo():
    v = vacante(requisitos=(("excel", 1), ("ingles", 1)))
    cs = [curso("a", semanas=4), curso("b", otorga=(("ingles", 1),), turnos=(Turno.tarde,), semanas=6)]
    assert planificar(joven(), [v], cs, MATRIZ).semanas_total == 6


def test_plan_reproducible():
    v = vacante(requisitos=(("excel", 1), ("ingles", 1)))
    cs = [curso(f"c{i}", otorga=(("excel", 1), ("ingles", 1)), costo=10) for i in range(5)]
    primero = planificar(joven(), [v], cs, MATRIZ).model_dump()
    for _ in range(3):
        assert planificar(joven(), [v], cs, MATRIZ).model_dump() == primero


# ---------- Varios jóvenes compitiendo por cupos ----------

def test_grupo_descuenta_cupos():
    planes = planificar_grupo([joven("a"), joven("b")], [vacante()], [curso("unico", cupos=1)], MATRIZ)
    assert sorted(len(p.cursos) for p in planes) == [0, 1]


def test_grupo_da_el_cupo_a_quien_tiene_menos_opciones():
    # "a" tiene dos vacantes alcanzables; "b" solo una (le falta el turno de tarde para v2).
    v1 = vacante("v1")
    v2 = vacante("v2", turnos={Turno.tarde})
    a = joven("a")
    b = joven("b", disponibilidad={Turno.manana})
    planes = {p.joven_id: p for p in planificar_grupo([a, b], [v1, v2], [curso("unico", cupos=1)], MATRIZ)}
    assert planes["b"].cursos == ["unico"] and planes["a"].cursos == []
