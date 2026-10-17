"""Pruebas de la auditoría contrafactual del matching.

Distinguen tres cosas:

- **Guardas estructurales:** que la identidad no forme parte de lo que ve el solver y
  que el auditor no dependa de `DatosPersonales`.
- **Contrafactual de corregimiento:** las habilidades no deben moverse al cambiar de
  lugar; traslado y salario sí pueden (se comprueban por separado).
- **Validación del resultado global:** factibilidad, cupos, unicidad, `sin_asignar` y
  desgloses reproducibles. No se marca un matching legítimo restringido por interés.
"""
import importlib
import inspect

import pytest
from pydantic import Field

from agentes.auditor import Auditor
from agentes.auditor import contrafactual
from agentes.auditor.contrafactual import CAMPOS_IDENTIDAD, firma_matching
from agentes.matching import MatrizTraslados, asignar, evaluar
from contrato.modelos import (
    Asignacion, DatosPersonales, Desglose, EstadoVacante, Genero, HabilidadNivel, Joven,
    Pesos, RequisitoHabilidad, ResultadoMatching, Traslado, Turno, Vacante,
)

MATRIZ = MatrizTraslados([
    Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.00),
    Traslado(origen="la_chorrera", destino="bella_vista", minutos=70, costo=1.60),
    Traslado(origen="arraijan", destino="bella_vista", minutos=50, costo=1.25),
    Traslado(origen="la_chorrera", destino="tocumen", minutos=115, costo=2.10),
])


def joven(id="j1", corregimiento="la_chorrera", habilidades=(("caja", 1),), **cambios):
    datos = dict(id=id, corregimiento=corregimiento,
                 disponibilidad={Turno.manana, Turno.tarde},
                 presupuesto_transporte_semanal=20, salario_minimo=500,
                 habilidades=[HabilidadNivel(codigo=c, nivel=n) for c, n in habilidades])
    datos.update(cambios)
    return Joven(**datos)


def vacante(id="v1", corregimiento="arraijan", requisitos=(("caja", 1, True),), **cambios):
    datos = dict(id=id, empresa_id="e1", titulo="Puesto", corregimiento=corregimiento,
                 turnos={Turno.manana}, salario_mensual=650, dias_por_semana=5,
                 estado=EstadoVacante.publicada,
                 habilidades_requeridas=[RequisitoHabilidad(codigo=c, nivel_minimo=n, obligatoria=o)
                                         for c, n, o in requisitos])
    datos.update(cambios)
    return Vacante(**datos)


def datos(joven_id="j1", nombre="Alguien", genero=Genero.femenino, edad=20):
    return DatosPersonales(joven_id=joven_id, nombre=nombre, genero=genero, edad=edad)


def resultado_vacio():
    return ResultadoMatching(asignaciones=[], sin_asignar=[], infactibles=[])


def aprobado(resultados, objeto_id):
    r = next(x for x in resultados if x.objeto_id == objeto_id)
    return r.aprobado, r.hallazgos


# ---------- 1. guardas estructurales de identidad ----------

def test_el_solver_no_recibe_identidad():
    for fn in (evaluar, asignar):
        assert not (set(inspect.signature(fn).parameters) & set(CAMPOS_IDENTIDAD))
    assert not (set(joven().model_dump()) & set(CAMPOS_IDENTIDAD))


def test_la_guardia_de_identidad_dispara_si_aparece_un_campo():
    class JovenConNombre(Joven):
        nombre: str = Field(default="x")

    hallazgos = contrafactual.contrafactual_identidad(JovenConNombre(**joven().model_dump()))
    assert any(h.regla == "contrafactual_identidad" for h in hallazgos)


def test_los_datos_personales_no_afectan_la_auditoria():
    j = joven("j1")
    vs = [vacante("v1")]
    r = asignar([j], vs, MATRIZ)
    d_ana = {j.id: datos(j.id, nombre="Ana", genero=Genero.femenino)}
    d_zulay = {j.id: datos(j.id, nombre="Zulay", genero=Genero.masculino)}
    a_ana = [x.model_dump() for x in Auditor().auditar_matching(r, [j], d_ana, vs, MATRIZ)]
    a_zulay = [x.model_dump() for x in Auditor().auditar_matching(r, [j], d_zulay, vs, MATRIZ)]
    assert a_ana == a_zulay


# ---------- 2. contrafactual de corregimiento ----------

def test_corregimiento_mantiene_habilidades_y_mueve_traslado_y_salario():
    v = vacante("v1", corregimiento="arraijan", requisitos=(("caja", 1, True),))
    cerca = evaluar(joven("j1", "la_chorrera", habilidades=(("caja", 2),)), v, MATRIZ)
    lejos = evaluar(joven("j1", "bella_vista", habilidades=(("caja", 2),)), v, MATRIZ)

    assert isinstance(cerca, Desglose) and isinstance(lejos, Desglose)
    assert cerca.habilidades == lejos.habilidades == 1.0     # invariante
    assert cerca.traslado != lejos.traslado                  # puede moverse
    assert cerca.salario != lejos.salario                    # puede moverse


def test_el_auditor_aprueba_el_cambio_de_corregimiento():
    js = [joven("j1", "la_chorrera", habilidades=(("caja", 2),)),
          joven("j2", "bella_vista", habilidades=(("caja", 2),))]
    v = vacante("v1", corregimiento="arraijan")
    resultados = Auditor().auditar_matching(asignar(js, [v], MATRIZ), js, {}, [v], MATRIZ)
    assert aprobado(resultados, "j1") == (True, [])
    assert aprobado(resultados, "j2") == (True, [])


def test_el_auditor_marca_habilidades_dependientes_del_corregimiento(monkeypatch):
    v = vacante("v1", corregimiento="arraijan")

    def evaluar_tramposo(j, vac, matriz, pesos=None):
        d = evaluar(j, vac, matriz, pesos)
        if not isinstance(d, Desglose):
            return d
        return d.model_copy(update={"habilidades": 1.0 if j.corregimiento == "la_chorrera" else 0.5})

    monkeypatch.setattr(contrafactual, "evaluar", evaluar_tramposo)
    hallazgos = contrafactual.contrafactual_corregimiento(
        joven("j1", "la_chorrera"), [v], MATRIZ)
    assert any(h.regla == "contrafactual_corregimiento" for h in hallazgos)


def test_mutacion_habilidades_por_corregimiento_en_el_puntaje_real(monkeypatch):
    pmod = importlib.import_module("agentes.matching.puntaje")
    original = pmod.puntaje

    def tramposo(j, v, matriz, pesos=None):
        d = original(j, v, matriz, pesos)
        return d.model_copy(update={"habilidades": 1.0 if j.corregimiento == "la_chorrera" else 0.4})

    monkeypatch.setattr(pmod, "puntaje", tramposo)
    v = vacante("v1", corregimiento="arraijan")
    hallazgos = contrafactual.contrafactual_corregimiento(joven("j1", "la_chorrera"), [v], MATRIZ)
    assert any(h.regla == "contrafactual_corregimiento" for h in hallazgos)


def test_corregimiento_sin_datos_de_traslado_no_aporta_evidencia():
    # 'zona_sin_datos' no está en la matriz: mover allí es infactible y se omite.
    # La lista vacía NO significa "no hay sesgo": significa que no hubo nada que comparar.
    v = vacante("v1", corregimiento="arraijan")
    hallazgos = contrafactual.contrafactual_corregimiento(
        joven("j1", "la_chorrera"), [v], MATRIZ, corregimientos=["zona_sin_datos"])
    assert hallazgos == []


# ---------- 3. validación global del resultado ----------

def test_acepta_un_resultado_limpio():
    js = [joven("a", "la_chorrera", habilidades=(("caja", 1), ("ventas", 1))),
          joven("b", "la_chorrera", habilidades=(("caja", 1),))]
    v1 = vacante("v1", corregimiento="la_chorrera", requisitos=(("caja", 1, True),))
    v2 = vacante("v2", corregimiento="arraijan", requisitos=(("ventas", 1, True),))
    r = asignar(js, [v1, v2], MATRIZ)
    assert {(x.joven_id, x.vacante_id) for x in r.asignaciones} == {("a", "v2"), ("b", "v1")}
    assert aprobado(Auditor().auditar_matching(r, js, {}, [v1, v2], MATRIZ),
                    "asignacion_global") == (True, [])


def test_acepta_un_resultado_restringido_por_interes_mutuo():
    a = joven("a", "la_chorrera", habilidades=(("caja", 1), ("ventas", 1)))
    b = joven("b", "la_chorrera", habilidades=(("caja", 1),))
    v1 = vacante("v1", corregimiento="la_chorrera", requisitos=(("caja", 1, True),))
    v2 = vacante("v2", corregimiento="arraijan", requisitos=(("ventas", 1, True),))
    # El óptimo sin restricciones sería {a→v2, b→v1}; solo (b, v1) tiene interés mutuo.
    restringido = asignar([a, b], [v1, v2], MATRIZ, permitidos={("b", "v1")})
    assert [(x.joven_id, x.vacante_id) for x in restringido.asignaciones] == [("b", "v1")]
    # Restringir por interés es legítimo: no debe marcarse.
    assert aprobado(Auditor().auditar_matching(restringido, [a, b], {}, [v1, v2], MATRIZ),
                    "asignacion_global") == (True, [])


def test_detecta_par_infactible_asignado():
    j = joven("j1", "la_chorrera", habilidades=(("caja", 2),))
    base = evaluar(j, vacante("v0", corregimiento="arraijan", requisitos=(("caja", 1, True),)), MATRIZ)
    v_lejos = vacante("v1", corregimiento="tocumen", requisitos=(("caja", 1, True),))
    falso = ResultadoMatching(asignaciones=[Asignacion(joven_id="j1", vacante_id="v1", desglose=base)],
                              sin_asignar=[], infactibles=[])
    hallazgos = contrafactual.contrafactual_asignacion_global(falso, [j], [v_lejos], MATRIZ)
    assert any(x.regla == "contrafactual_desglose" for x in hallazgos)


def test_detecta_cupos_excedidos():
    j1 = joven("j1", "la_chorrera", habilidades=(("caja", 1),))
    j2 = joven("j2", "la_chorrera", habilidades=(("caja", 1),))
    v = vacante("v1", corregimiento="arraijan", cupos=1, requisitos=(("caja", 1, True),))
    d = evaluar(j1, v, MATRIZ)
    falso = ResultadoMatching(
        asignaciones=[Asignacion(joven_id="j1", vacante_id="v1", desglose=d),
                      Asignacion(joven_id="j2", vacante_id="v1", desglose=d)],
        sin_asignar=[], infactibles=[])
    hallazgos = contrafactual.contrafactual_asignacion_global(falso, [j1, j2], [v], MATRIZ)
    assert any("cupos" in x.detalle for x in hallazgos)


def test_detecta_joven_asignado_dos_veces():
    j = joven("j1", "la_chorrera", habilidades=(("caja", 1),))
    v1 = vacante("v1", corregimiento="arraijan", requisitos=(("caja", 1, True),))
    v2 = vacante("v2", corregimiento="bella_vista", requisitos=(("caja", 1, True),))
    falso = ResultadoMatching(
        asignaciones=[Asignacion(joven_id="j1", vacante_id="v1", desglose=evaluar(j, v1, MATRIZ)),
                      Asignacion(joven_id="j1", vacante_id="v2", desglose=evaluar(j, v2, MATRIZ))],
        sin_asignar=[], infactibles=[])
    hallazgos = contrafactual.contrafactual_asignacion_global(falso, [j], [v1, v2], MATRIZ)
    assert any("más de una vez" in x.detalle for x in hallazgos)


def test_detecta_sin_asignar_incoherente():
    j = joven("j1")
    v = vacante("v1")
    real = asignar([j], [v], MATRIZ)
    falso = ResultadoMatching(asignaciones=real.asignaciones, sin_asignar=["j1"],
                              infactibles=real.infactibles)
    hallazgos = contrafactual.contrafactual_asignacion_global(falso, [j], [v], MATRIZ)
    assert any("sin_asignar" in x.detalle for x in hallazgos)


def test_detecta_desglose_manipulado():
    j, v = joven("j1"), vacante("v1")
    real = asignar([j], [v], MATRIZ)
    manipulada = real.asignaciones[0].model_copy(
        update={"desglose": real.asignaciones[0].desglose.model_copy(update={"total": 0.999})})
    falso = ResultadoMatching(asignaciones=[manipulada], sin_asignar=real.sin_asignar,
                              infactibles=real.infactibles)
    assert any(x.regla == "contrafactual_desglose"
               for x in contrafactual.contrafactual_asignacion_global(falso, [j], [v], MATRIZ))
    assert aprobado(Auditor().auditar_matching(falso, [j], {}, [v], MATRIZ),
                    "asignacion_global")[0] is False


def test_firma_matching_distingue_asignaciones():
    j = joven("j1")
    v1 = vacante("v1", corregimiento="arraijan")
    v2 = vacante("v2", corregimiento="tocumen")
    d = evaluar(j, v1, MATRIZ)
    uno = ResultadoMatching(asignaciones=[Asignacion(joven_id="j1", vacante_id="v1", desglose=d)],
                            sin_asignar=[], infactibles=[])
    otro = ResultadoMatching(asignaciones=[Asignacion(joven_id="j1", vacante_id="v2", desglose=d)],
                             sin_asignar=[], infactibles=[])
    ninguno = ResultadoMatching(asignaciones=[], sin_asignar=["j1"], infactibles=[])
    assert firma_matching(uno) != firma_matching(otro)
    assert firma_matching(uno) != firma_matching(ninguno)


# ---------- 4. entradas inválidas y errores ----------

def test_matriz_ausente_con_vacantes_lanza_error():
    with pytest.raises(ValueError):
        Auditor().auditar_matching(None, [joven("j1")], {}, [vacante("v1")], None)


def test_sin_resultado_no_emite_el_global():
    resultados = Auditor().auditar_matching(None, [joven("j1")], {}, [], MATRIZ)
    assert [r.objeto_id for r in resultados] == ["j1"]


def test_resultado_vacio_emite_el_global_aprobado():
    resultados = Auditor().auditar_matching(resultado_vacio(), [], {}, [], None)
    assert [r.objeto_id for r in resultados] == ["asignacion_global"]
    assert resultados[0].aprobado is True


# ---------- 5. forma de la salida y determinismo ----------

def test_emite_un_resultado_por_joven_mas_el_global():
    js = [joven("j1"), joven("j2")]
    v = vacante("v1")
    r = Auditor().auditar_matching(asignar(js, [v], MATRIZ), js, {}, [v], MATRIZ)
    assert {x.objeto_id for x in r} == {"j1", "j2", "asignacion_global"}
    assert all(x.tipo == "contrafactual" for x in r)


def test_auditoria_determinista():
    js = [joven(f"j{i}") for i in range(3)]
    vs = [vacante("v1", cupos=2), vacante("v2", corregimiento="la_chorrera")]
    r = asignar(js, vs, MATRIZ)
    primera = [x.model_dump() for x in Auditor().auditar_matching(r, js, {}, vs, MATRIZ)]
    for _ in range(3):
        assert [x.model_dump() for x in Auditor().auditar_matching(r, js, {}, vs, MATRIZ)] == primera


# ---------- 6. validación de pesos recibidos vs. declarados ----------

def resultado_con(j, v, desglose, sin_asignar=()):
    return ResultadoMatching(
        asignaciones=[Asignacion(joven_id=j.id, vacante_id=v.id, desglose=desglose)],
        sin_asignar=list(sin_asignar), infactibles=[])


def test_pesos_recibidos_iguales_a_los_del_desglose_se_aprueban():
    pesos = Pesos(habilidades=0.50, traslado=0.30, salario=0.20)
    j = joven("j1", "la_chorrera", habilidades=(("caja", 2),))
    v = vacante("v1", corregimiento="arraijan")
    r = asignar([j], [v], MATRIZ, pesos=pesos)
    assert r.asignaciones[0].desglose.pesos == pesos
    assert aprobado(Auditor().auditar_matching(r, [j], {}, [v], MATRIZ, pesos),
                    "asignacion_global") == (True, [])


def test_pesos_recibidos_distintos_a_los_del_desglose_se_reportan():
    calculados = Pesos(habilidades=0.50, traslado=0.30, salario=0.20)
    recibidos = Pesos(habilidades=0.60, traslado=0.25, salario=0.15)
    j = joven("j1", "la_chorrera", habilidades=(("caja", 2),))
    v = vacante("v1", corregimiento="arraijan")
    desglose = evaluar(j, v, MATRIZ, calculados)
    assert desglose.pesos == calculados

    aprobado_sino, hallazgos = aprobado(
        Auditor().auditar_matching(resultado_con(j, v, desglose), [j], {}, [v], MATRIZ, recibidos),
        "asignacion_global")
    assert aprobado_sino is False
    assert any(h.regla == "contrafactual_pesos" for h in hallazgos)
    # El total sigue cuadrando con los pesos que el propio desglose declara.
    assert not any(h.regla == "contrafactual_desglose" for h in hallazgos)


def test_desglose_sin_pesos_no_se_da_por_validado():
    j = joven("j1", "la_chorrera", habilidades=(("caja", 2),))
    v = vacante("v1", corregimiento="arraijan")
    sin_pesos = evaluar(j, v, MATRIZ).model_copy(update={"pesos": None})

    aprobado_sino, hallazgos = aprobado(
        Auditor().auditar_matching(resultado_con(j, v, sin_pesos), [j], {}, [v], MATRIZ),
        "asignacion_global")
    assert aprobado_sino is False
    assert any(h.regla == "contrafactual_desglose" and "no se puede validar" in h.detalle
               for h in hallazgos)


def test_desglose_sin_pesos_se_valida_con_los_recibidos():
    pesos = Pesos()
    j = joven("j1", "la_chorrera", habilidades=(("caja", 2),))
    v = vacante("v1", corregimiento="arraijan")
    sin_pesos = evaluar(j, v, MATRIZ, pesos).model_copy(update={"pesos": None})

    assert aprobado(Auditor().auditar_matching(resultado_con(j, v, sin_pesos), [j], {}, [v],
                                               MATRIZ, pesos),
                    "asignacion_global") == (True, [])


def test_total_sin_pesos_es_no_verificable_no_falso():
    d = Desglose(habilidades=1.0, traslado=0.5, salario=0.5, total=0.75)
    assert contrafactual._total_incoherente(d, None) is None
    assert contrafactual._total_incoherente(d, Pesos()) is True
    assert contrafactual._total_incoherente(d.model_copy(update={"pesos": Pesos()})) is True
