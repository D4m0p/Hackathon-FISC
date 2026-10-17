"""Pruebas del arnes de evals (no del sistema de produccion).

Verifican que el arnes sea robusto: que un error inesperado no aborte la
evaluacion en silencio, que el reporte marque la corrida como no satisfactoria y
que nunca se confunda con uno anterior. Se ejecutan con:
    python -m pytest evals/test_evals.py -q
(`pytest.ini` limita la suite general a `tests/`, por eso se pasan aqui.)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import evals.correr as correr  # noqa: E402
import evals.metricas as metricas  # noqa: E402


def _caso(asunto="detector"):
    return {"id": "x", "asunto": asunto, "categoria": asunto, "naturaleza": "determinista",
            "descripcion": "caso de prueba", "entrada": {}, "esperado": {"tipo": "aprueba"}}


# --- 1. Un error inesperado no aborta la evaluacion ---------------------------

def test_excepcion_inesperada_no_aborta(monkeypatch):
    def boom(_caso):
        raise RuntimeError("fallo simulado del sistema")

    monkeypatch.setitem(correr.ASUNTOS, "detector", boom)
    resultados = correr.ejecutar([_caso()])       # no debe propagar la excepcion

    assert len(resultados) == 1
    r = resultados[0]
    assert r["cumplido"] is False
    assert r["error"] is True
    assert r["obs"]["tipo"] == "error_inesperado"
    assert r["obs"]["excepcion"] == "RuntimeError"
    assert "RuntimeError" in r["detalle"]


def test_estado_no_satisfactoria_con_error(monkeypatch):
    monkeypatch.setitem(correr.ASUNTOS, "detector",
                        lambda _c: (_ for _ in ()).throw(RuntimeError("x")))
    resultados = correr.ejecutar([_caso()])
    assert correr._estado(resultados) == "no_satisfactoria"


def test_estado_satisfactoria_sin_errores(monkeypatch):
    monkeypatch.setitem(correr.ASUNTOS, "detector",
                        lambda _c: {"tipo": "oferta", "aprobado": True, "reglas": []})
    resultados = correr.ejecutar([_caso()])
    assert correr._estado(resultados) == "satisfactoria"


# --- 2. El reporte refleja el error y el estado ------------------------------

def test_reporte_marca_corrida_no_satisfactoria(monkeypatch):
    monkeypatch.setitem(correr.ASUNTOS, "detector",
                        lambda _c: (_ for _ in ()).throw(RuntimeError("boom-reporte")))
    resultados = correr.ejecutar([_caso()])
    reporte = correr.construir_reporte(resultados, correr._estado(resultados))

    assert "NO SATISFACTORIA" in reporte
    assert "Errores de evaluacion" in reporte
    assert "boom-reporte" in reporte


# --- 3. El reporte no puede confundirse con uno anterior ---------------------

def test_reporte_en_curso_reemplaza_uno_anterior(tmp_path):
    ruta = tmp_path / "resultados.md"
    ruta.write_text("REPORTE VIEJO: todo pasa", encoding="utf-8")

    correr.escribir_reporte(correr.reporte_en_curso(), ruta)

    contenido = ruta.read_text(encoding="utf-8")
    assert "REPORTE VIEJO" not in contenido
    assert "EN CURSO" in contenido


def test_main_deja_reporte_en_curso_si_aborta(tmp_path, monkeypatch):
    ruta = tmp_path / "resultados.md"
    ruta.write_text("REPORTE VIEJO: todo pasa", encoding="utf-8")
    monkeypatch.setattr(correr, "RUTA_RESULTADOS", ruta)

    def morir(_casos):
        raise RuntimeError("caida antes de terminar")

    monkeypatch.setattr(correr, "ejecutar", morir)
    with pytest.raises(RuntimeError):
        correr.main([])

    contenido = ruta.read_text(encoding="utf-8")
    assert "REPORTE VIEJO" not in contenido
    assert "EN CURSO" in contenido


def test_main_genera_reporte_satisfactorio(tmp_path, monkeypatch):
    ruta = tmp_path / "resultados.md"
    monkeypatch.setattr(correr, "RUTA_RESULTADOS", ruta)

    codigo = correr.main([])

    contenido = ruta.read_text(encoding="utf-8")
    assert codigo == 0
    assert "SATISFACTORIA" in contenido and "NO SATISFACTORIA" not in contenido
    assert "EN CURSO" not in contenido


# --- 4. sin_hallazgo exige ausencia total de hallazgos -----------------------

def _caso_contrafactual():
    caso = _caso("contrafactual")
    caso["entrada"] = {}
    caso["esperado"] = {"tipo": "sin_hallazgo", "reglas": ["contrafactual_corregimiento"]}
    return caso


def _obs(hallazgos, aprobado=True, igual_datos=None):
    obs = {"tipo": "hallazgos", "aprobado": aprobado, "hallazgos": hallazgos}
    if igual_datos is not None:
        obs["igual_datos"] = igual_datos
    return obs


def test_sin_hallazgo_acepta_salida_limpia():
    cumplido, _ = metricas.comparar(_caso_contrafactual(), _obs([]))
    assert cumplido is True


def test_sin_hallazgo_rechaza_hallazgo_inesperado():
    obs = _obs([["asignacion_global", "otra_regla"]])
    cumplido, detalle = metricas.comparar(_caso_contrafactual(), obs)
    assert cumplido is False
    assert "inesperados" in detalle


def test_sin_hallazgo_rechaza_global_no_aprobado():
    cumplido, _ = metricas.comparar(_caso_contrafactual(), _obs([], aprobado=False))
    assert cumplido is False


# --- 5. Mercado no mezcla guardrails en sus metricas ------------------------

def _resultado(asunto, categoria, esperado, obs):
    return {"id": "x", "asunto": asunto, "categoria": categoria, "naturaleza": "determinista",
            "etiqueta": None, "esperado": esperado, "obs": obs, "cumplido": True,
            "detalle": "", "determinista": True, "error": False}


def test_mercado_excluye_guardrails_de_sus_metricas():
    mercado = _resultado("mercado", "mercado",
                         {"tipo": "vacante", "codigos": ["manejo_caja"]},
                         {"tipo": "vacante", "codigos": ["manejo_caja"]})
    guardrail = _resultado("mercado", "guardrails",
                           {"tipo": "vacante", "codigos": ["manejo_caja"]},
                           {"tipo": "vacante", "codigos": ["piloto_avion"]})
    resumen = metricas.resumen([mercado, guardrail])

    assert resumen["mercado"]["precision"] == 1.0
    assert resumen["mercado"]["exhaustividad"] == 1.0
