"""Ejecuta los casos de `evals/casos/` contra el sistema real y escribe `resultados.md`.

No modifica el comportamiento de produccion: solo lo observa. Corre cada caso dos
veces y compara para verificar que sea determinista. Se ejecuta sin red (se quita
`GROQ_API_KEY`), de modo que el agente de Mercado use su respaldo por palabras clave
salvo que el caso inyecte una respuesta simulada.

Uso:
    python evals/correr.py            # escribe evals/resultados.md
    python evals/correr.py --json     # imprime el resumen en JSON
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ.pop("GROQ_API_KEY", None)

from pydantic import ValidationError  # noqa: E402

from evals import metricas, mundo  # noqa: E402
from agentes.auditor import Auditor  # noqa: E402
from agentes.matching import asignar, evaluar  # noqa: E402
from agentes.mercado import ErrorMercado, Mercado, OfertaIncompleta  # noqa: E402
from contrato.modelos import Infactible  # noqa: E402

DIR_CASOS = RAIZ / "evals" / "casos"
RUTA_RESULTADOS = RAIZ / "evals" / "resultados.md"


# --- Observadores por asunto -------------------------------------------------

def _observar_matching(resultado, jovenes, vacantes, matriz, pesos) -> dict:
    por_vacante = {v.id: v for v in vacantes}
    por_joven = {j.id: j for j in jovenes}
    conteo: dict[str, int] = {}
    incompatibles = 0
    infactibles_asignadas = 0
    for a in resultado.asignaciones:
        conteo[a.vacante_id] = conteo.get(a.vacante_id, 0) + 1
        v = por_vacante.get(a.vacante_id)
        j = por_joven.get(a.joven_id)
        if v is not None and j is not None:
            niveles = {h.codigo: h.nivel for h in j.habilidades}
            for req in v.habilidades_requeridas:
                if req.obligatoria and niveles.get(req.codigo, 0) < req.nivel_minimo:
                    incompatibles += 1
                    break
            if isinstance(evaluar(j, v, matriz, pesos), Infactible):
                infactibles_asignadas += 1
    violaciones = sum(1 for vid, n in conteo.items() if vid in por_vacante and n > por_vacante[vid].cupos)
    return {
        "tipo": "asignacion",
        "asignaciones": sorted([a.joven_id, a.vacante_id] for a in resultado.asignaciones),
        "sin_asignar": sorted(resultado.sin_asignar),
        "infactibles": len(resultado.infactibles),
        "asignaciones_infactibles": infactibles_asignadas,
        "violaciones_cupos": violaciones,
        "incompatibles": incompatibles,
    }


def correr_matching(caso: dict) -> dict:
    entrada = caso["entrada"]
    try:
        jovenes = [mundo.joven(j) for j in entrada.get("jovenes", [])]
        vacantes = [mundo.vacante(v) for v in entrada.get("vacantes", [])]
    except ValidationError as ex:
        return {"tipo": "error_controlado", "excepcion": "ValidationError", "detalle": str(ex)[:300]}
    matriz = mundo.matriz(entrada.get("traslados"))
    pesos = mundo.pesos(entrada.get("pesos"))
    resultado = asignar(jovenes, vacantes, matriz, pesos=pesos)
    return _observar_matching(resultado, jovenes, vacantes, matriz, pesos)


def correr_detector(caso: dict) -> dict:
    vacante = mundo.vacante(caso["entrada"]["vacante"])
    resultado = Auditor().auditar_oferta(vacante)
    return {"tipo": "oferta", "aprobado": resultado.aprobado,
            "reglas": sorted({h.regla for h in resultado.hallazgos})}


def _mutar(resultado, mutacion, jovenes, vacantes, matriz, pesos):
    if mutacion != "par_infactible" or not resultado.asignaciones:
        return resultado
    joven = jovenes[0]
    infactible = next(
        (v for v in vacantes if isinstance(evaluar(joven, v, matriz, pesos), Infactible)), None)
    if infactible is None:
        return resultado
    original = resultado.asignaciones[0]
    manipulada = original.model_copy(update={"vacante_id": infactible.id})
    return resultado.model_copy(update={"asignaciones": [manipulada]})


def correr_contrafactual(caso: dict) -> dict:
    entrada = caso["entrada"]
    matriz = None if entrada.get("matriz", "pendiente") is None else mundo.matriz(entrada.get("traslados"))
    jovenes = [mundo.joven(j) for j in entrada.get("jovenes", [])]
    vacantes = [mundo.vacante(v) for v in entrada.get("vacantes", [])]
    datos = mundo.datos_personales(entrada.get("datos"))
    pesos = mundo.pesos(entrada.get("pesos"))
    resultado = mundo.resultado(entrada.get("resultado"))
    if resultado is None and matriz is not None:
        resultado = asignar(jovenes, vacantes, matriz, pesos=pesos)
        resultado = _mutar(resultado, entrada.get("mutacion"), jovenes, vacantes, matriz, pesos)
    try:
        salida = Auditor().auditar_matching(resultado, jovenes, datos, vacantes, matriz, pesos)
    except ValueError as ex:
        return {"tipo": "error_controlado", "excepcion": "ValueError", "detalle": str(ex)}

    observado = {
        "tipo": "hallazgos",
        "aprobado": all(r.aprobado for r in salida),
        "hallazgos": sorted([r.objeto_id, h.regla] for r in salida for h in r.hallazgos),
    }
    if entrada.get("datos_alternativo") is not None:
        alterno = mundo.datos_personales(entrada["datos_alternativo"])
        salida2 = Auditor().auditar_matching(resultado, jovenes, alterno, vacantes, matriz, pesos)
        observado["igual_datos"] = _normalizar(salida) == _normalizar(salida2)
    return observado


class _LLM:
    def __init__(self, respuesta):
        self.respuesta = respuesta

    def json(self, sistema, usuario):
        return self.respuesta


def correr_mercado(caso: dict) -> dict:
    entrada = caso["entrada"]
    cliente = _LLM(entrada["llm"]) if entrada.get("llm") is not None else None
    mercadotecnia = Mercado(cliente=cliente)
    try:
        vacante = mercadotecnia.normalizar_oferta(entrada["texto"], entrada.get("empresa_id", "e1"))
    except OfertaIncompleta as ex:
        return {"tipo": "error_controlado", "excepcion": "OfertaIncompleta", "campos": sorted(ex.campos)}
    except ErrorMercado as ex:
        return {"tipo": "error_controlado", "excepcion": "ErrorMercado", "detalle": str(ex)}
    return {
        "tipo": "vacante",
        "codigos": sorted(r.codigo for r in vacante.habilidades_requeridas),
        "corregimiento": vacante.corregimiento,
        "turnos": sorted(t.value for t in vacante.turnos),
    }


ASUNTOS = {
    "matching": correr_matching,
    "detector": correr_detector,
    "contrafactual": correr_contrafactual,
    "mercado": correr_mercado,
}


# --- Orquestacion ------------------------------------------------------------

def _normalizar(valor) -> str:
    if isinstance(valor, list):
        valor = [v.model_dump(mode="json") if hasattr(v, "model_dump") else v for v in valor]
    return json.dumps(valor, sort_keys=True, ensure_ascii=False, default=str)


def ejecutar(casos: list[dict]) -> list[dict]:
    """Corre cada caso dos veces y arma el resultado observado.

    Nunca deja que un fallo inesperado aborte la corrida: lo convierte en un
    resultado identificable como error de evaluacion (`cumplido=False`,
    `error=True`) para que quede en el reporte.
    """
    resultados = []
    for caso in casos:
        correr = ASUNTOS[caso["asunto"]]
        try:
            obs1 = correr(caso)
            obs2 = correr(caso)
            determinista = _normalizar(obs1) == _normalizar(obs2)
            cumplido, detalle = metricas.comparar(caso, obs1)
            error = False
        except Exception as ex:  # error inesperado del sistema o del caso
            obs1 = {"tipo": "error_inesperado", "excepcion": type(ex).__name__,
                    "detalle": str(ex)[:300]}
            obs2 = None
            determinista = False
            cumplido = False
            error = True
            detalle = f"error inesperado al ejecutar: {type(ex).__name__}: {str(ex)[:160]}"
        resultados.append({
            "id": caso["id"],
            "asunto": caso["asunto"],
            "categoria": caso["categoria"],
            "naturaleza": caso["naturaleza"],
            "etiqueta": caso.get("etiqueta"),
            "descripcion": caso["descripcion"],
            "esperado": caso["esperado"],
            "obs": obs1,
            "cumplido": cumplido,
            "detalle": detalle,
            "determinista": determinista,
            "error": error,
        })
    return resultados


def _estado(resultados: list[dict]) -> str:
    """`satisfactoria` solo si todos cumplen y no hubo errores de evaluacion."""
    return "satisfactoria" if (resultados and all(r["cumplido"] for r in resultados)
                               and not any(r.get("error") for r in resultados)) else "no_satisfactoria"


# --- Reporte -----------------------------------------------------------------

def _pct(valor) -> str:
    return "N/A" if valor is None else f"{valor * 100:.1f}%"


def _tabla_conteo(titulo, conteo) -> list[str]:
    lineas = [f"### {titulo}", "", "| Clave | Casos | Cumplen |", "|---|---|---|"]
    for clave, c in conteo.items():
        lineas.append(f"| {clave} | {c['total']} | {c['cumplido']} |")
    lineas.append("")
    return lineas


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True,
                              check=False).stdout.strip()
    except OSError:
        return ""


def _fecha() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def escribir_reporte(contenido: str, ruta: Path | None = None) -> None:
    (ruta or RUTA_RESULTADOS).write_text(contenido, encoding="utf-8")


def reporte_en_curso() -> str:
    """Marca de corrida: reemplaza cualquier reporte anterior mientras se ejecuta.

    Si el proceso muere a mitad de camino, este texto (con fecha fresca y estado
    EN CURSO) queda en el archivo, de modo que un reporte viejo nunca se presenta
    como si fuera el resultado actual.
    """
    commit = _git(["rev-parse", "--short", "HEAD"]) or "(sin git)"
    return "\n".join([
        "# Resultados de los evals",
        "",
        "- Estado de la corrida: **EN CURSO / INCOMPLETA**",
        f"- Iniciada: {_fecha()}",
        f"- Commit: `{commit}` · Python {platform.python_version()}",
        "",
        "La evaluacion no ha terminado; este archivo no refleja un resultado valido.",
        "Si queda asi, la corrida se interrumpio: vuelva a ejecutar `python evals/correr.py`.",
        "",
    ])


def construir_reporte(resultados: list[dict], estado: str | None = None) -> str:
    estado = estado or _estado(resultados)
    resumen = metricas.resumen(resultados)
    cumplen = sum(int(r["cumplido"]) for r in resultados)
    errores = [r for r in resultados if r.get("error")]
    fecha = _fecha()
    commit = _git(["rev-parse", "--short", "HEAD"]) or "(sin git)"
    etiqueta_estado = "SATISFACTORIA" if estado == "satisfactoria" else "NO SATISFACTORIA"

    lineas = [
        "# Resultados de los evals",
        "",
        f"- Estado de la corrida: **{etiqueta_estado}**",
        f"- Generado por `python evals/correr.py`: {fecha}",
        f"- Commit: `{commit}` · Python {platform.python_version()} · sin red (`GROQ_API_KEY` retirada)",
        f"- Casos ejecutados: **{len(resultados)}** · cumplen: **{cumplen}** "
        f"· errores de evaluacion: **{len(errores)}**",
        "",
        "Cada caso se ejecuto dos veces y se compararon las salidas normalizadas para "
        "verificar que sea determinista. Los casos de `naturaleza: revision_humana` se "
        "consideran correctos cuando el sistema los deriva a revision en vez de decidir solo.",
        "",
    ]

    lineas += ["## Errores de evaluacion (fallo inesperado)", ""]
    if errores:
        for r in errores:
            lineas.append(f"- `{r['id']}` ({r['asunto']}): {r['detalle'].replace(chr(10), ' ')}")
    else:
        lineas.append("Ninguno.")
    lineas.append("")

    lineas += [
        "## Casos",
        "",
        "| id | asunto | categoria | naturaleza | resultado | detalle |",
        "|---|---|---|---|---|---|",
    ]
    for r in resultados:
        marca = "cumple" if r["cumplido"] else "**no cumple**"
        detalle = r["detalle"].replace("\n", " ")
        if not r["determinista"]:
            detalle += " · NO DETERMINISTA"
        lineas.append(f"| {r['id']} | {r['asunto']} | {r['categoria']} | "
                      f"{r['naturaleza']} | {marca} | {detalle} |")
    lineas.append("")

    lineas += _tabla_conteo("Por categoria", resumen["por_categoria"])
    lineas += _tabla_conteo("Por asunto", resumen["por_asunto"])

    m = resumen["matching"]
    d = resumen["detector"]
    mc = resumen["mercado"]
    lineas += [
        "## Metricas agregadas",
        "",
        "| Metrica | Valor |",
        "|---|---|",
        f"| Asignaciones observadas | {m['asignaciones']} |",
        f"| Factibilidad de asignaciones | {_pct(m['factibilidad'])} |",
        f"| Violaciones de cupos | {m['violaciones_cupos']} |",
        f"| Asignaciones incompatibles con habilidades | {m['incompatibles']} |",
        f"| Detector: precision | {_pct(d['precision'])} (tp={d['tp']}, fp={d['fp']}) |",
        f"| Detector: exhaustividad | {_pct(d['exhaustividad'])} (fn={d['fn']}, tn={d['tn']}) |",
        f"| Mercado: precision de habilidades (categoria mercado) | {_pct(mc['precision'])} |",
        f"| Mercado: exhaustividad de habilidades (categoria mercado) | {_pct(mc['exhaustividad'])} |",
        f"| Contrafactuales cumplidos | {resumen['contrafactuales']['cumplido']}/"
        f"{resumen['contrafactuales']['total']} |",
        f"| Guardrails cumplidos | {resumen['guardrails']['cumplido']}/{resumen['guardrails']['total']} |",
        f"| Entradas malformadas contenidas | {resumen['malformadas']['cumplido']}/{resumen['malformadas']['total']} |",
        "",
    ]

    fallos = [r for r in resultados if not r["cumplido"]]
    lineas += ["## Errores funcionales (expectativa no cumplida)", ""]
    if fallos:
        for r in fallos:
            lineas.append(f"- `{r['id']}` ({r['categoria']}): {r['detalle'].replace(chr(10), ' ')}")
    else:
        lineas.append("Ninguno.")
    lineas.append("")

    revision = [r for r in resultados if r["naturaleza"] == "revision_humana"]
    lineas += ["## Casos derivados a revision humana", ""]
    if revision:
        for r in revision:
            correcto = "correctamente derivado" if r["cumplido"] else "NO derivado como se esperaba"
            lineas.append(f"- `{r['id']}`: {correcto} ({r['detalle'].replace(chr(10), ' ')})")
    else:
        lineas.append("Ninguno.")
    lineas.append("")

    no_det = resumen["no_deterministas"]
    lineas += ["## Determinismo", ""]
    lineas.append("Todas las salidas fueron reproducibles." if not no_det
                  else "Casos no reproducibles: " + ", ".join(f"`{i}`" for i in no_det))
    lineas.append("")

    lineas += [
        "## Limitaciones",
        "",
        "- Los evals ejercitan los agentes directamente (matching, auditor, mercado); no cubren",
        "  la API ni el frontend.",
        "- La ruta de formacion queda fuera del alcance inicial.",
        "- El agente de Mercado corre sin red: cuando el caso no inyecta una respuesta simulada,",
        "  usa su respaldo por palabras clave, asi que no mide calidad del modelo de lenguaje real.",
        "- Las metricas sin ejemplos suficientes se reportan como N/A.",
        "",
    ]
    return "\n".join(lineas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Ejecuta los evals y escribe resultados.md")
    parser.add_argument("--json", action="store_true", help="imprime el resumen en JSON")
    args = parser.parse_args(argv)

    escribir_reporte(reporte_en_curso())   # invalida cualquier reporte anterior
    casos = mundo.cargar_casos(DIR_CASOS)
    resultados = ejecutar(casos)
    estado = _estado(resultados)
    escribir_reporte(construir_reporte(resultados, estado))

    resumen = metricas.resumen(resultados)
    cumplen = sum(int(r["cumplido"]) for r in resultados)
    if args.json:
        print(json.dumps({"casos": len(resultados), "cumplen": cumplen, "estado": estado, **resumen},
                         indent=2, ensure_ascii=False, default=str))
    else:
        try:
            ubicacion = RUTA_RESULTADOS.relative_to(RAIZ)
        except ValueError:
            ubicacion = RUTA_RESULTADOS
        print(f"[{estado}] {cumplen}/{len(resultados)} casos cumplen. Reporte en {ubicacion}.")
        for r in resultados:
            if not r["cumplido"]:
                print(f"  - {r['id']}: {r['detalle'].replace(chr(10), ' ')}")
    return 0 if estado == "satisfactoria" else 1


if __name__ == "__main__":
    raise SystemExit(main())