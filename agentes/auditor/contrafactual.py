"""Auditoría contrafactual del matching: ¿la identidad cambia la decisión?

Se recalcula todo con el código real de `agentes/matching` (`evaluar`, `asignar`);
no se inventan puntajes.

Tres cambios que NO deberían influir en el resultado salvo en los componentes
legítimos:

- **Nombre y género:** viven en `DatosPersonales`, nunca en `Joven`, que es lo único
  que ve el solver (ver `contrato/modelos.py`). `contrafactual_identidad` es una
  **guarda estructural**: solo comprueba que la identidad no forme parte de `Joven`.
  No es una prueba conductual de ausencia de sesgo; para eso haría falta que el
  solver recibiera la identidad, cosa que el contrato impide a propósito.
- **Corregimiento:** el solver sí lo ve, pero solo puede mover los componentes
  `traslado` y `salario`. `habilidades` no depende del lugar; si cambia, hay un sesgo
  real que el orientador debe revisar. Un cambio de asignación por cercanía es
  legítimo y no se marca.
- **Resultado global:** se valida su integridad (pares factibles, cupos, unicidad,
  `sin_asignar` coherente y desglose reproducible con los pesos que el propio
  desglose declara). No se exige que coincida con el óptimo sin restricciones,
  porque el matching real filtra por interés mutuo y la interfaz no entrega ese
  conjunto de pares permitidos.
"""
from __future__ import annotations

from agentes.matching import asignar, es_factible, evaluar
from contrato.modelos import (
    Desglose, EstadoVacante, Hallazgo, Joven, Pesos, ResultadoMatching, Vacante,
)

# Campos que describen a la persona y no al trabajo; no deben llegar al solver.
CAMPOS_IDENTIDAD = ("nombre", "genero", "edad", "contacto_telegram")

# Los totales del desglose se redondean a 4 decimales; se admite ese margen.
_TOLERANCIA_DESGLOSE = 1e-3


def validar_entradas(vacantes: list[Vacante], matriz) -> None:
    """Falla rápido si falta la matriz que el cálculo necesita (no se aprueba en falso)."""
    if matriz is None and vacantes:
        raise ValueError("auditar_matching necesita la matriz de traslados para evaluar vacantes")


def desgloses_de_joven(joven: Joven, vacantes: list[Vacante], matriz,
                       pesos: Pesos | None = None) -> dict[str, Desglose]:
    """Desglose real por vacante publicada y factible para ese joven."""
    desgloses: dict[str, Desglose] = {}
    for v in vacantes:
        if v.estado != EstadoVacante.publicada or not es_factible(joven, v, matriz):
            continue   # sin armar la explicación de un par imposible (mismo resultado, mucho más rápido)
        d = evaluar(joven, v, matriz, pesos)
        if isinstance(d, Desglose):
            desgloses[v.id] = d
    return desgloses


def corregimientos_de(jovenes: list[Joven], vacantes: list[Vacante]) -> list[str]:
    return sorted({j.corregimiento for j in jovenes} | {v.corregimiento for v in vacantes})


def firma_matching(resultado: ResultadoMatching):
    """Resumen comparable de una asignación: pares con su total y quién queda sin asignar."""
    return (
        tuple(sorted((a.joven_id, a.vacante_id, a.desglose.total) for a in resultado.asignaciones)),
        tuple(sorted(resultado.sin_asignar)),
    )


def contrafactual_identidad(joven: Joven) -> list[Hallazgo]:
    """Guarda estructural: la identidad no debe formar parte de lo que ve el solver."""
    recibidos = [c for c in CAMPOS_IDENTIDAD if c in joven.model_dump()]
    if not recibidos:
        return []
    return [Hallazgo(
        regla="contrafactual_identidad",
        detalle=(f"El solver recibe datos de identidad de {joven.id}: {sorted(recibidos)}. "
                 "El puntaje no debe depender de ellos."),
        sugerencia="Mantenga la identidad en DatosPersonales, fuera de Joven.")]


def contrafactual_corregimiento(joven: Joven, vacantes: list[Vacante], matriz,
                                pesos: Pesos | None = None,
                                corregimientos: list[str] | None = None) -> list[Hallazgo]:
    """`habilidades` no debe cambiar al mover al joven de corregimiento.

    Solo se comparan los pares factibles en ambos corregimientos. Si un corregimiento
    alterno no tiene datos de traslado, se omite; la lista vacía de hallazgos no debe
    leerse como prueba de ausencia de sesgo cuando no hubo nada que comparar.
    """
    if corregimientos is None:
        corregimientos = corregimientos_de([joven], vacantes)
    base = desgloses_de_joven(joven, vacantes, matriz, pesos)
    for c in corregimientos:
        if c == joven.corregimiento:
            continue
        copia = joven.model_copy(update={"corregimiento": c})
        for vacante_id, d in desgloses_de_joven(copia, vacantes, matriz, pesos).items():
            b = base.get(vacante_id)
            if b is None:
                continue
            if abs(b.habilidades - d.habilidades) > 1e-9:
                return [Hallazgo(
                    regla="contrafactual_corregimiento",
                    detalle=(f"Mover a {joven.id} de '{joven.corregimiento}' a '{c}' cambia el "
                             f"componente de habilidades en la vacante {vacante_id} "
                             f"(de {b.habilidades} a {d.habilidades}); no debe depender del lugar."),
                    sugerencia="Revise que el puntaje de habilidades no use el corregimiento.")]
    return []


def contrafactual_desglose(resultado: ResultadoMatching | None, jovenes: list[Joven],
                           vacantes: list[Vacante], matriz,
                           pesos: Pesos | None = None) -> list[Hallazgo]:
    """Cada asignación debe ser factible y su desglose reproducible con el código real.

    - Los componentes `habilidades`, `traslado` y `salario` no dependen de los pesos, así
      que se comparan siempre.
    - Si el auditor recibe `pesos` explícitos, se exige que el `Desglose` declare esos
      mismos pesos; si declara otros, se reporta `contrafactual_pesos`.
    - El `total` se valida contra los pesos declarados en el propio `Desglose` y, si este
      no los declara, contra los recibidos. Cuando no hay pesos por ningún lado el total
      **no puede darse por validado** y se reporta como no verificable.
    """
    if resultado is None:
        return []
    por_id = {j.id: j for j in jovenes}
    vac = {v.id: v for v in vacantes}
    hallazgos: list[Hallazgo] = []
    for a in resultado.asignaciones:
        j, v = por_id.get(a.joven_id), vac.get(a.vacante_id)
        if j is None or v is None:
            continue   # los pares desconocidos se reportan en la validación global
        real = evaluar(j, v, matriz, pesos)
        if not isinstance(real, Desglose):
            hallazgos.append(Hallazgo(
                regla="contrafactual_desglose",
                detalle=(f"El par {a.joven_id}→{a.vacante_id} aparece asignado pero es "
                         "infactible según el matching."),
                sugerencia="Revise la asignación: no debería incluir pares infactibles."))
            continue
        if pesos is not None and a.desglose.pesos is not None and not _pesos_iguales(a.desglose.pesos, pesos):
            hallazgos.append(Hallazgo(
                regla="contrafactual_pesos",
                detalle=(f"El desglose de {a.joven_id}→{a.vacante_id} declara pesos "
                         f"({a.desglose.pesos.habilidades}/{a.desglose.pesos.traslado}/"
                         f"{a.desglose.pesos.salario}) distintos de los recibidos "
                         f"({pesos.habilidades}/{pesos.traslado}/{pesos.salario})."),
                sugerencia="Recalcule el puntaje con los pesos vigentes del orientador."))
        componentes = (abs(real.habilidades - a.desglose.habilidades) > 1e-9
                       or abs(real.traslado - a.desglose.traslado) > 1e-9
                       or abs(real.salario - a.desglose.salario) > 1e-9)
        estado_total = _total_incoherente(a.desglose, pesos)
        if componentes or estado_total is True:
            hallazgos.append(Hallazgo(
                regla="contrafactual_desglose",
                detalle=(f"El desglose de {a.joven_id}→{a.vacante_id} no coincide con el "
                         "recálculo real (componentes o total)."),
                sugerencia="Recalcule el puntaje con `evaluar` para la asignación mostrada."))
        elif estado_total is None:
            hallazgos.append(Hallazgo(
                regla="contrafactual_desglose",
                detalle=(f"El desglose de {a.joven_id}→{a.vacante_id} no declara pesos y la "
                         "auditoría no recibió pesos: el total no se puede validar."),
                sugerencia="Guarde los pesos con los que se calculó el desglose (`Desglose.pesos`)."))
    return hallazgos


def _pesos_iguales(a: Pesos, b: Pesos) -> bool:
    return (abs(a.habilidades - b.habilidades) <= 1e-9
            and abs(a.traslado - b.traslado) <= 1e-9
            and abs(a.salario - b.salario) <= 1e-9)


def _total_incoherente(d: Desglose, pesos: Pesos | None = None) -> bool | None:
    """Coherencia de `d.total` con sus componentes.

    Devuelve `True` si no cuadra, `False` si cuadra y `None` si no hay con qué validarlo
    (el `Desglose` no declara pesos y la auditoría tampoco los recibió). `None` no es un
    aprobado: significa "no verificable".
    """
    efectivos = d.pesos if d.pesos is not None else pesos
    if efectivos is None:
        return None
    esperado = (efectivos.habilidades * d.habilidades + efectivos.traslado * d.traslado
                + efectivos.salario * d.salario)
    return abs(esperado - d.total) > _TOLERANCIA_DESGLOSE


def contrafactual_asignacion_global(resultado: ResultadoMatching | None, jovenes: list[Joven],
                                    vacantes: list[Vacante], matriz,
                                    pesos: Pesos | None = None) -> list[Hallazgo]:
    """Valida invariantes globales que todo `resultado` legítimo cumple.

    - cada par asignado es factible y de una vacante publicada;
    - cada joven aparece a lo sumo una vez y no se superan los cupos;
    - `sin_asignar` es exactamente el conjunto de jóvenes sin asignación;
    - cada desglose es reproducible (ver `contrafactual_desglose`).

    No se compara con el óptimo sin restricciones: el matching filtra por interés
    mutuo y esos pares no llegan en la interfaz. Por eso una asignación distinta
    pero internamente coherente no se puede distinguir aquí de una legítima.
    """
    if resultado is None:
        return []
    por_id = {j.id: j for j in jovenes}
    vac = {v.id: v for v in vacantes}
    hallazgos = contrafactual_desglose(resultado, jovenes, vacantes, matriz, pesos)

    conteo_joven: dict[str, int] = {}
    conteo_vacante: dict[str, int] = {}
    for a in resultado.asignaciones:
        j, v = por_id.get(a.joven_id), vac.get(a.vacante_id)
        if j is None:
            hallazgos.append(_hallazgo_asignacion(
                f"La asignación menciona al joven desconocido {a.joven_id}."))
            continue
        if v is None:
            hallazgos.append(_hallazgo_asignacion(
                f"La asignación menciona la vacante desconocida {a.vacante_id}."))
            continue
        conteo_joven[a.joven_id] = conteo_joven.get(a.joven_id, 0) + 1
        conteo_vacante[a.vacante_id] = conteo_vacante.get(a.vacante_id, 0) + 1
        if v.estado != EstadoVacante.publicada:
            hallazgos.append(_hallazgo_asignacion(
                f"La vacante {v.id} no está publicada pero aparece asignada."))

    repetidos = sorted(k for k, n in conteo_joven.items() if n > 1)
    if repetidos:
        hallazgos.append(_hallazgo_asignacion(
            f"Jóvenes asignados más de una vez: {repetidos}."))
    excedidas = sorted(vid for vid, n in conteo_vacante.items()
                       if vid in vac and n > vac[vid].cupos)
    if excedidas:
        hallazgos.append(_hallazgo_asignacion(
            f"Vacantes con más asignaciones que cupos: {excedidas}."))

    asignados = {a.joven_id for a in resultado.asignaciones}
    esperado = sorted(j.id for j in jovenes if j.id not in asignados)
    if sorted(resultado.sin_asignar) != esperado:
        hallazgos.append(_hallazgo_asignacion(
            f"`sin_asignar` no coincide: informado {sorted(resultado.sin_asignar)}, "
            f"esperado {esperado}."))
    return hallazgos


def _hallazgo_asignacion(detalle: str) -> Hallazgo:
    return Hallazgo(
        regla="contrafactual_asignacion", detalle=detalle,
        sugerencia="Confirme la asignación volviendo a ejecutar el matching.")


def hallazgos_de_joven(joven: Joven, vacantes: list[Vacante], matriz,
                       pesos: Pesos | None = None,
                       corregimientos: list[str] | None = None) -> list[Hallazgo]:
    return (contrafactual_identidad(joven)
            + contrafactual_corregimiento(joven, vacantes, matriz, pesos, corregimientos))


__all__ = [
    "CAMPOS_IDENTIDAD", "contrafactual_asignacion_global", "contrafactual_corregimiento",
    "contrafactual_desglose", "contrafactual_identidad", "corregimientos_de",
    "desgloses_de_joven", "firma_matching", "hallazgos_de_joven", "validar_entradas",
]
