"""Factibilidad y puntaje explicable de un par joven–vacante.

Todo es código determinístico: el LLM no interviene aquí.
Componentes que dependen de la geografía: `traslado` y `salario` (el salario se
mide neto del costo de transporte). `habilidades` no depende del lugar. El
Auditor usa esta separación en sus pruebas contrafactuales.
"""
from __future__ import annotations

from contrato.modelos import (
    Desglose, Incumplimiento, Infactible, Joven, Pesos, TipoIncumplimiento, Vacante,
)

from .traslados import MatrizTraslados, costo_mensual, costo_semanal

PESOS = Pesos()   # valores por defecto; el orientador puede ajustarlos
SALARIO_REFERENCIA = 900.0   # B/. mensual netos con los que el componente llega a 1
PESO_OBLIGATORIA = 2
PESO_OPCIONAL = 1


def _niveles(joven: Joven) -> dict[str, int]:
    niveles: dict[str, int] = {}
    for h in joven.habilidades:
        niveles[h.codigo] = max(niveles.get(h.codigo, 0), h.nivel)
    return niveles


def incumplimientos(joven: Joven, vacante: Vacante, matriz: MatrizTraslados) -> list[Incumplimiento]:
    """Restricciones que no se cumplen, con su magnitud. Lista vacía = factible."""
    fallas: list[Incumplimiento] = []
    viaje = matriz.viaje(joven.corregimiento, vacante.corregimiento)
    if viaje is None:
        fallas.append(Incumplimiento(
            tipo=TipoIncumplimiento.sin_datos,
            detalle=f"No hay datos de traslado entre {joven.corregimiento} y {vacante.corregimiento}"))
    else:
        if viaje.minutos > joven.max_minutos_traslado:
            fallas.append(Incumplimiento(
                tipo=TipoIncumplimiento.traslado, faltante=viaje.minutos - joven.max_minutos_traslado,
                detalle=f"El traslado toma {viaje.minutos} min y su límite es {joven.max_minutos_traslado} min"))
        semanal = costo_semanal(viaje, vacante.dias_por_semana)
        if semanal > joven.presupuesto_transporte_semanal:
            fallas.append(Incumplimiento(
                tipo=TipoIncumplimiento.presupuesto,
                faltante=round(semanal - joven.presupuesto_transporte_semanal, 2),
                detalle=f"El transporte cuesta B/.{semanal:.2f} por semana y su presupuesto es "
                        f"B/.{joven.presupuesto_transporte_semanal:.2f}"))
    faltan_turnos = vacante.turnos - joven.disponibilidad
    if faltan_turnos:
        nombres = ", ".join(sorted(t.value for t in faltan_turnos))
        fallas.append(Incumplimiento(
            tipo=TipoIncumplimiento.horario, codigo=nombres, faltante=len(faltan_turnos),
            detalle=f"El horario pide turnos que no tiene disponibles: {nombres}"))
    if vacante.salario_mensual < joven.salario_minimo:
        fallas.append(Incumplimiento(
            tipo=TipoIncumplimiento.salario, faltante=round(joven.salario_minimo - vacante.salario_mensual, 2),
            detalle=f"El salario B/.{vacante.salario_mensual:.2f} es menor que su mínimo "
                    f"B/.{joven.salario_minimo:.2f}"))
    niveles = _niveles(joven)
    for r in vacante.habilidades_requeridas:
        if r.obligatoria and niveles.get(r.codigo, 0) < r.nivel_minimo:
            fallas.append(Incumplimiento(
                tipo=TipoIncumplimiento.habilidad, codigo=r.codigo,
                faltante=r.nivel_minimo - niveles.get(r.codigo, 0),
                detalle=f"Falta la habilidad obligatoria {r.codigo} (nivel {r.nivel_minimo})"))
    return fallas


def motivos_infactible(joven: Joven, vacante: Vacante, matriz: MatrizTraslados) -> list[str]:
    """Lista vacía = el par es factible."""
    return [f.detalle for f in incumplimientos(joven, vacante, matriz)]


def puntaje(joven: Joven, vacante: Vacante, matriz: MatrizTraslados,
            pesos: Pesos | None = None) -> Desglose:
    """Supone que el par es factible (llamar antes a `motivos_infactible`)."""
    viaje = matriz.viaje(joven.corregimiento, vacante.corregimiento)
    assert viaje is not None, "puntaje() solo se usa con pares factibles"
    niveles = _niveles(joven)
    motivos: list[str] = []

    total_peso = cumplido = 0
    for r in vacante.habilidades_requeridas:
        peso = PESO_OBLIGATORIA if r.obligatoria else PESO_OPCIONAL
        total_peso += peso
        if niveles.get(r.codigo, 0) >= r.nivel_minimo:
            cumplido += peso
            motivos.append(f"Tiene {r.codigo}")
    habilidades = 1.0 if total_peso == 0 else cumplido / total_peso

    traslado = max(0.0, 1 - viaje.minutos / joven.max_minutos_traslado)
    motivos.append(f"Traslado de {viaje.minutos} min, B/.{costo_semanal(viaje, vacante.dias_por_semana):.2f} por semana")

    neto = vacante.salario_mensual - costo_mensual(viaje, vacante.dias_por_semana)
    salario = min(1.0, max(0.0, neto / SALARIO_REFERENCIA))
    motivos.append(f"Salario neto de transporte: B/.{neto:.2f} al mes")

    p = pesos or PESOS
    total = p.habilidades * habilidades + p.traslado * traslado + p.salario * salario
    return Desglose(habilidades=round(habilidades, 4), traslado=round(traslado, 4),
                    salario=round(salario, 4), total=round(total, 4), motivos=motivos, pesos=p)


def evaluar(joven: Joven, vacante: Vacante, matriz: MatrizTraslados,
            pesos: Pesos | None = None) -> Desglose | Infactible:
    motivos = motivos_infactible(joven, vacante, matriz)
    if motivos:
        return Infactible(joven_id=joven.id, vacante_id=vacante.id, motivos=motivos)
    return puntaje(joven, vacante, matriz, pesos)
