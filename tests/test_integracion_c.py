"""Puntos de integración que pidió C (Diego): el Auditor recibe los mismos pesos que el
matching, y una oferta incompleta del Mercado responde 422 con los campos que faltan."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.main import crear_app
from contrato.modelos import Asignacion, Pesos, Traslado
from orquestador import Almacen, Orquestador
from orquestador.interfaces import OfertaIncompleta
from tests.test_orquestador import AuditorFalso, NotificadorFalso, joven, vacante

VIERNES = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)
CERCANIA = Pesos(habilidades=0.2, traslado=0.7, salario=0.1)


class AuditorQueAnotaPesos(AuditorFalso):
    def __init__(self):
        super().__init__()
        self.pesos_recibidos = []

    def auditar_matching(self, resultado, jovenes, datos, vacantes, matriz, pesos=None):
        self.pesos_recibidos.append(pesos)
        return []


class AuditorConKwargs(AuditorFalso):
    def __init__(self):
        super().__init__()
        self.kwargs = None

    def auditar_matching(self, *args, **kwargs):
        self.kwargs = kwargs
        return []


def sistema(auditor, mercado=None):
    o = Orquestador(Almacen(), mercado=mercado, auditor=auditor, notificador=NotificadorFalso(),
                    reloj=lambda: VIERNES)
    o.almacen.guardar_traslados([Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0)])
    o.registrar_joven(joven())
    o.publicar_vacante(vacante())
    o.deslizar("joven", "j1", "v1", True)
    o.deslizar("empresa", "j1", "v1", True)
    return o


# ---------- pesos: matching y Auditor usan los mismos ----------

def test_el_auditor_recibe_los_pesos_que_uso_el_matching():
    auditor = AuditorQueAnotaPesos()
    o = sistema(auditor)
    o.ejecutar_matching()
    o.cambiar_pesos(CERCANIA, "Priorizar cercanía")
    o.ejecutar_matching()
    assert auditor.pesos_recibidos == [Pesos(), CERCANIA]
    usados = [a.desglose.pesos for a in o.almacen.listar(Asignacion) if a.vigente]
    assert usados == [CERCANIA]                       # el mismo valor que vio el Auditor


def test_un_auditor_con_kwargs_tambien_recibe_los_pesos():
    auditor = AuditorConKwargs()
    sistema(auditor).ejecutar_matching()
    assert auditor.kwargs == {"pesos": Pesos()}


def test_un_auditor_de_la_version_anterior_sigue_funcionando():
    sistema(AuditorFalso()).ejecutar_matching()       # firma sin `pesos`: no se rompe


# ---------- oferta incompleta del Mercado → 422 ----------

class MercadoIncompleto:
    def normalizar_oferta(self, texto, empresa_id):
        raise OfertaIncompleta(["salario_mensual", "turnos"])


class OfertaIncompletaPropia(Exception):
    """Clase con el mismo nombre que podría tener el Mercado de C (transición)."""


OfertaIncompletaPropia.__name__ = "OfertaIncompleta"


class MercadoConClasePropia:
    def normalizar_oferta(self, texto, empresa_id):
        e = OfertaIncompletaPropia("Faltan datos")
        e.campos = ["corregimiento"]
        raise e


class MercadoRoto:
    def normalizar_oferta(self, texto, empresa_id):
        raise RuntimeError("falla interna")


def cliente(mercado):
    o = Orquestador(Almacen(), mercado=mercado)
    o.almacen.guardar_credencial("t-e1", "empresa", "e1")
    return TestClient(crear_app(o)), o


OFERTA = {"texto": "Se busca cajero con experiencia", "empresa_id": "e1"}
CABECERA = {"Authorization": "Bearer t-e1"}


def test_oferta_incompleta_responde_422_con_los_campos_que_faltan():
    c, o = cliente(MercadoIncompleto())
    r = c.post("/ofertas", json=OFERTA, headers=CABECERA)
    assert r.status_code == 422
    assert r.json()["faltantes"] == ["salario_mensual", "turnos"]
    assert "salario_mensual" in r.json()["detail"]
    t = o.almacen.trazas("mercado")[0]
    assert t.accion == "oferta_incompleta" and t.salida["faltantes"] == ["salario_mensual", "turnos"]


def test_la_clase_propia_del_mercado_tambien_da_422():
    c, _ = cliente(MercadoConClasePropia())
    r = c.post("/ofertas", json=OFERTA, headers=CABECERA)
    assert r.status_code == 422 and r.json()["faltantes"] == ["corregimiento"]


def test_otros_errores_del_mercado_no_se_disfrazan_de_422():
    c, _ = cliente(MercadoRoto())
    with pytest.raises(RuntimeError):
        c.post("/ofertas", json=OFERTA, headers=CABECERA)
