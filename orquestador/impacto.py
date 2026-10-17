"""Cifra de impacto: cuántas combinaciones joven–vacante descarta el sistema y por qué."""
from pydantic import BaseModel

from agentes.matching import es_factible, incumplimientos
from contrato.modelos import EstadoVacante, Joven, TipoIncumplimiento, Vacante


class Descartes(BaseModel):
    traslado: int = 0
    presupuesto: int = 0
    horario: int = 0
    salario: int = 0
    habilidad: int = 0
    sin_datos: int = 0


class Impacto(BaseModel):
    jovenes: int
    vacantes_publicadas: int
    pares: int
    viables: int
    descartes: Descartes   # un par suma en cada motivo que incumple
    pares_con_un_solo_motivo: int


class ImpactoJoven(BaseModel):
    joven_id: str
    publicadas: int
    viables: int
    descartes: Descartes


def _publicadas(orq) -> list[Vacante]:
    return [v for v in orq.almacen.listar(Vacante) if v.estado == EstadoVacante.publicada]


def _evaluar(joven: Joven, vacantes: list[Vacante], matriz) -> tuple[int, dict[str, int], int]:
    """(viables, descartes por tipo, no viables con un solo motivo) de un joven."""
    viables = un_solo_motivo = 0
    cuenta = {t.value: 0 for t in TipoIncumplimiento}
    for v in vacantes:
        if es_factible(joven, v, matriz):
            viables += 1
            continue
        tipos = {i.tipo for i in incumplimientos(joven, v, matriz)}
        for t in tipos:
            cuenta[t.value] += 1
        if len(tipos) == 1:
            un_solo_motivo += 1
    return viables, cuenta, un_solo_motivo


def impacto(orq) -> Impacto:
    jovenes = orq.almacen.listar(Joven)
    vacantes = _publicadas(orq)
    matriz = orq.matriz()
    viables = un_solo_motivo = 0
    total = {t.value: 0 for t in TipoIncumplimiento}
    for j in jovenes:
        v, cuenta, uno = _evaluar(j, vacantes, matriz)
        viables += v
        un_solo_motivo += uno
        for k, n in cuenta.items():
            total[k] += n
    return Impacto(jovenes=len(jovenes), vacantes_publicadas=len(vacantes),
                   pares=len(jovenes) * len(vacantes), viables=viables,
                   descartes=Descartes(**total), pares_con_un_solo_motivo=un_solo_motivo)


def impacto_joven(orq, joven_id: str) -> ImpactoJoven:
    joven = orq._joven(joven_id)
    vacantes = _publicadas(orq)
    viables, cuenta, _ = _evaluar(joven, vacantes, orq.matriz())
    return ImpactoJoven(joven_id=joven_id, publicadas=len(vacantes), viables=viables,
                        descartes=Descartes(**cuenta))
