"""Agenda determinística de entrevistas."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from contrato.modelos import Joven, Turno, Vacante

PANAMA = ZoneInfo("America/Panama")
HORA_INICIO = {Turno.manana: time(9), Turno.tarde: time(14), Turno.noche: time(18),
               Turno.fin_de_semana: time(10)}
ORDEN = [Turno.manana, Turno.tarde, Turno.noche, Turno.fin_de_semana]
DURACION = timedelta(minutes=30)


def proxima_entrevista(joven: Joven, vacante: Vacante, desde: datetime,
                       ocupados: set[datetime] = frozenset()) -> datetime:
    """Primer espacio libre desde el día siguiente, en el primer turno que
    comparten el joven y la vacante. Si el espacio está ocupado, corre 30 min."""
    comunes = [t for t in ORDEN if t in vacante.turnos and t in joven.disponibilidad]
    if not comunes:
        raise ValueError("El joven y la vacante no comparten ningún turno")
    turno = comunes[0]
    dia = desde.astimezone(PANAMA).date() + timedelta(days=1)
    entre_semana = turno != Turno.fin_de_semana
    while (dia.weekday() >= 5) == entre_semana:
        dia += timedelta(days=1)
    hora = datetime.combine(dia, HORA_INICIO[turno], tzinfo=PANAMA)
    while hora in ocupados:
        hora += DURACION
    return hora
