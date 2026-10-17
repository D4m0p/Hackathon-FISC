import json
import sys

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from agentes.matching import es_factible
from api.rutas_impacto import crear_router
from api.seguridad import Identidad, dependencias, sin_permiso
from contrato.modelos import (
    EstadoVacante, HabilidadNivel, Joven, RequisitoHabilidad, Traslado, Turno, Vacante,
)
from orquestador import Almacen, NoEncontrado, Orquestador
from orquestador.impacto import impacto, impacto_joven

sys.path.insert(0, "scripts")
from semilla_demo import DATOS, cargar  # noqa: E402


def vacante(id="v1", **cambios):
    datos = dict(id=id, empresa_id="e1", titulo="Cajero", corregimiento="arraijan",
                 turnos={Turno.manana}, salario_mensual=650,
                 habilidades_requeridas=[RequisitoHabilidad(codigo="caja")])
    datos.update(cambios)
    return Vacante(**datos)


def joven(id="j1", **cambios):
    datos = dict(id=id, corregimiento="la_chorrera", disponibilidad={Turno.manana, Turno.tarde},
                 presupuesto_transporte_semanal=20, salario_minimo=500,
                 habilidades=[HabilidadNivel(codigo="caja", nivel=1)])
    datos.update(cambios)
    return Joven(**datos)


@pytest.fixture
def orq():
    almacen = Almacen()
    almacen.guardar_traslados([
        Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0),
        Traslado(origen="la_chorrera", destino="tocumen", minutos=110, costo=2.5),
    ])
    return Orquestador(almacen)


def test_sin_datos_da_ceros(orq):
    i = impacto(orq)
    assert (i.jovenes, i.vacantes_publicadas, i.pares, i.viables) == (0, 0, 0, 0)
    assert i.pares_con_un_solo_motivo == 0


def test_par_viable(orq):
    orq.registrar_joven(joven())
    orq.publicar_vacante(vacante())
    i = impacto(orq)
    assert (i.pares, i.viables, i.pares_con_un_solo_motivo) == (1, 1, 0)
    assert i.descartes.model_dump() == dict.fromkeys(i.descartes.model_dump(), 0)


def test_falla_solo_por_traslado(orq):
    orq.registrar_joven(joven(presupuesto_transporte_semanal=100))   # el pasaje no es problema
    orq.publicar_vacante(vacante(corregimiento="tocumen"))
    i = impacto(orq)
    assert i.viables == 0
    assert i.descartes.traslado == 1
    assert i.pares_con_un_solo_motivo == 1


def test_traslado_y_salario_cuentan_en_ambos(orq):
    orq.registrar_joven(joven())
    orq.publicar_vacante(vacante(corregimiento="tocumen", salario_mensual=400))
    i = impacto(orq)
    assert i.viables == 0
    assert i.descartes.traslado == 1 and i.descartes.salario == 1
    assert i.pares_con_un_solo_motivo == 0


def test_sin_datos_de_traslado(orq):
    orq.registrar_joven(joven(corregimiento="colon"))
    orq.publicar_vacante(vacante())
    i = impacto(orq)
    assert i.viables == 0
    assert i.descartes.sin_datos == 1
    assert i.pares_con_un_solo_motivo == 1


def test_vacante_no_publicada_no_cuenta(orq):
    orq.registrar_joven(joven())
    orq.publicar_vacante(vacante())
    orq.almacen.guardar(vacante("v2", estado=EstadoVacante.cerrada))
    i = impacto(orq)
    assert i.vacantes_publicadas == 1 and i.pares == 1


def test_impacto_joven(orq):
    orq.registrar_joven(joven())
    orq.publicar_vacante(vacante())
    orq.publicar_vacante(vacante("v2", corregimiento="tocumen"))
    r = impacto_joven(orq, "j1")
    assert (r.joven_id, r.publicadas, r.viables, r.descartes.traslado) == ("j1", 2, 1, 1)
    with pytest.raises(NoEncontrado):
        impacto_joven(orq, "nadie")


def test_coherencia_con_datos_de_demo():
    orq = Orquestador(Almacen())
    cargar(orq, json.loads(DATOS.read_text(encoding="utf-8")))
    i = impacto(orq)
    jovenes = orq.almacen.listar(Joven)
    publicadas = [v for v in orq.almacen.listar(Vacante) if v.estado == EstadoVacante.publicada]
    matriz = orq.matriz()
    a_mano = sum(es_factible(j, v, matriz) for j in jovenes for v in publicadas)
    assert i.pares == len(jovenes) * len(publicadas) == i.jovenes * i.vacantes_publicadas
    assert i.viables == a_mano
    no_viables = i.pares - i.viables
    assert i.pares_con_un_solo_motivo <= no_viables
    assert sum(i.descartes.model_dump().values()) >= no_viables
    por_joven = [impacto_joven(orq, j.id) for j in jovenes]
    assert sum(p.viables for p in por_joven) == i.viables
    assert all(p.publicadas == len(publicadas) for p in por_joven)


@pytest.fixture
def cliente(orq):
    orq.registrar_joven(joven("j1"))
    orq.registrar_joven(joven("j2"))
    orq.publicar_vacante(vacante())
    orq.almacen.guardar_credencial("t-ori", "orientador", None)
    orq.almacen.guardar_credencial("t-j1", "joven", "j1")
    _, requerida = dependencias(orq.almacen)

    def solo_orientador(ident: Identidad = Depends(requerida)) -> Identidad:
        if not ident.es_orientador:
            raise sin_permiso("Solo el orientador puede hacer esto")
        return ident

    app = FastAPI()
    app.include_router(crear_router(orq, solo_orientador, requerida))

    @app.exception_handler(NoEncontrado)
    async def _no_encontrado(_: Request, e: NoEncontrado):
        return JSONResponse(status_code=404, content={"detail": str(e)})

    return TestClient(app)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_rutas_orientador(cliente):
    r = cliente.get("/impacto", headers=auth("t-ori"))
    assert r.status_code == 200 and r.json()["pares"] == 2
    assert cliente.get("/jovenes/j2/impacto", headers=auth("t-ori")).status_code == 200


def test_rutas_joven(cliente):
    assert cliente.get("/jovenes/j1/impacto", headers=auth("t-j1")).status_code == 200
    assert cliente.get("/jovenes/j2/impacto", headers=auth("t-j1")).status_code == 403
    assert cliente.get("/impacto", headers=auth("t-j1")).status_code == 403


def test_rutas_sin_token_y_joven_inexistente(cliente):
    assert cliente.get("/impacto").status_code == 401
    assert cliente.get("/jovenes/j1/impacto").status_code == 401
    assert cliente.get("/jovenes/nadie/impacto", headers=auth("t-ori")).status_code == 404
