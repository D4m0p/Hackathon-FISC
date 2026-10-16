import json
import sys
from pathlib import Path

from agentes.formacion import casi_califica
from agentes.matching import MatrizTraslados, incumplimientos
from contrato.modelos import (
    Curso, EstadoVacante, HabilidadNivel, Joven, RequisitoHabilidad, TipoIncumplimiento, Traslado,
    Turno, Vacante,
)

MATRIZ = MatrizTraslados([
    Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.00),
    Traslado(origen="la_chorrera", destino="bella_vista", minutos=70, costo=1.60),
    Traslado(origen="la_chorrera", destino="tocumen", minutos=95, costo=1.50),
])


def joven(**cambios):
    datos = dict(id="j1", corregimiento="la_chorrera", disponibilidad={Turno.manana, Turno.tarde},
                 presupuesto_transporte_semanal=15, salario_minimo=550,
                 habilidades=[HabilidadNivel(codigo="caja", nivel=1)])
    datos.update(cambios)
    return Joven(**datos)


def vacante(id="v1", requisitos=(("caja", 1),), **cambios):
    datos = dict(id=id, empresa_id="e1", titulo=f"Puesto {id}", corregimiento="arraijan",
                 turnos={Turno.manana}, salario_mensual=650, estado=EstadoVacante.publicada,
                 habilidades_requeridas=[RequisitoHabilidad(codigo=c, nivel_minimo=n) for c, n in requisitos])
    datos.update(cambios)
    return Vacante(**datos)


def curso(id="c1", codigo="ventas", nivel=1, **cambios):
    datos = dict(id=id, centro="INADEH", nombre=f"Curso {id}", corregimiento="la_chorrera",
                 turnos={Turno.tarde}, sesiones_por_semana=2, semanas=4, cupos_disponibles=10,
                 habilidades_otorgadas=[HabilidadNivel(codigo=codigo, nivel=nivel)])
    datos.update(cambios)
    return Curso(**datos)


def tipos(resultado):
    return [(c.vacante_id, c.incumplimiento.tipo) for c in resultado]


# ---------- incumplimientos con magnitud ----------

def test_incumplimientos_miden_cuanto_falta():
    j = joven(presupuesto_transporte_semanal=15, salario_minimo=700)
    fallas = {f.tipo: f for f in incumplimientos(j, vacante(corregimiento="bella_vista"), MATRIZ)}
    assert fallas[TipoIncumplimiento.presupuesto].faltante == 1.00     # 16.00 - 15.00
    assert fallas[TipoIncumplimiento.salario].faltante == 50.00
    assert TipoIncumplimiento.traslado not in fallas                    # 70 min ≤ 75


def test_habilidad_que_falta_trae_su_codigo():
    f = incumplimientos(joven(), vacante(requisitos=(("ventas", 2),)), MATRIZ)
    assert [(x.tipo, x.codigo, x.faltante) for x in f] == [(TipoIncumplimiento.habilidad, "ventas", 2)]


# ---------- casi califica ----------

def test_solo_aparecen_vacantes_con_una_sola_falla():
    vs = [vacante("una", requisitos=(("ventas", 1),)),
          vacante("dos", requisitos=(("ventas", 1), ("excel", 1))),
          vacante("ninguna")]                                       # ya es factible
    assert [c.vacante_id for c in casi_califica(joven(), vs, [], MATRIZ)] == ["una"]


def test_falta_habilidad_sugiere_curso_viable_con_nombre_legible():
    r = casi_califica(joven(), [vacante(requisitos=(("ventas", 1),))], [curso()], MATRIZ,
                      nombres={"ventas": "Ventas"})
    assert r[0].cursos == ["c1"]
    assert "Le falta Ventas" in r[0].sugerencia and "4 semanas" in r[0].sugerencia


def test_curso_fuera_de_horario_no_se_sugiere():
    r = casi_califica(joven(), [vacante(requisitos=(("ventas", 1),))],
                      [curso(turnos={Turno.noche})], MATRIZ)
    assert r[0].cursos == [] and "ningún curso" in r[0].sugerencia


def test_curso_de_nivel_insuficiente_no_se_sugiere():
    r = casi_califica(joven(), [vacante(requisitos=(("ventas", 2),))], [curso(nivel=1)], MATRIZ)
    assert r[0].cursos == []


def test_curso_cuyo_pasaje_no_alcanza_no_se_sugiere():
    caro = curso(corregimiento="bella_vista", sesiones_por_semana=5)   # 1.60 x 2 x 5 = 16 > 15
    r = casi_califica(joven(), [vacante(requisitos=(("ventas", 1),))], [caro], MATRIZ)
    assert r[0].cursos == []


def test_presupuesto_dice_cuanto_falta():
    r = casi_califica(joven(), [vacante(corregimiento="bella_vista")], [], MATRIZ)
    assert tipos(r) == [("v1", TipoIncumplimiento.presupuesto)]
    assert "B/.1.00 por semana" in r[0].sugerencia


def test_traslado_dice_a_cuanto_ampliar_el_limite():
    r = casi_califica(joven(presupuesto_transporte_semanal=30), [vacante(corregimiento="tocumen")], [], MATRIZ)
    assert "ampl" in r[0].sugerencia and "95 min" in r[0].sugerencia


def test_horario_y_salario():
    vs = [vacante("h", turnos={Turno.noche}), vacante("s", salario_mensual=500)]
    r = casi_califica(joven(), vs, [], MATRIZ)
    assert set(tipos(r)) == {("h", TipoIncumplimiento.horario), ("s", TipoIncumplimiento.salario)}


def test_sin_datos_de_traslado_no_cuenta_como_casi():
    assert casi_califica(joven(corregimiento="boquete"), [vacante()], [], MATRIZ) == []


def test_borradores_y_cerradas_no_aparecen():
    vs = [vacante("b", requisitos=(("ventas", 1),), estado=EstadoVacante.borrador),
          vacante("c", requisitos=(("ventas", 1),), estado=EstadoVacante.cerrada)]
    assert casi_califica(joven(), vs, [curso()], MATRIZ) == []


def test_lo_accionable_va_primero():
    vs = [vacante("presupuesto", corregimiento="bella_vista"),
          vacante("con_curso", requisitos=(("ventas", 1),)),
          vacante("sin_curso", requisitos=(("soldadura", 1),))]
    orden = [c.vacante_id for c in casi_califica(joven(), vs, [curso()], MATRIZ)]
    assert orden == ["con_curso", "presupuesto", "sin_curso"]


# ---------- con los datos de la demo y por HTTP ----------

def test_maria_en_la_demo():
    from orquestador import Almacen, Orquestador
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from semilla_demo import DATOS, cargar
    orq = Orquestador(Almacen())
    cargar(orq, json.loads(DATOS.read_text(encoding="utf-8")))
    r = orq.casi_califica("j01")
    assert [c.vacante_id for c in r] == ["v05", "v10"]
    assert r[0].cursos == ["c01"] and "Técnicas de ventas" in r[0].sugerencia
    assert "Le falta Ventas" in r[0].sugerencia

    from conftest import cliente_orientador
    c = cliente_orientador(orq)
    assert c.get("/jovenes/j01/casi-califica").json()[1]["incumplimiento"]["faltante"] == 1.0
    assert c.get("/jovenes/nadie/casi-califica").status_code == 404
