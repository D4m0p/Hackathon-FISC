"""Evals del agente Perfil: corre casos/*.json y escribe resultados.md.

Uso (desde la raíz del repo):
    .venv/bin/python agentes/perfil/evals/correr.py            # sin red: LLM simulado o ausente
    .venv/bin/python agentes/perfil/evals/correr.py --en-vivo  # además, los casos «oro» con Groq real

Mismo formato que evals/ (casos con id, categoria, naturaleza, entrada y esperado; cada caso se
corre dos veces para verificar que sea determinista). El modo en vivo mide la calidad del modelo
real y no cuenta para el estado de la corrida, porque un LLM no es determinista.
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

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from agentes.perfil import ErrorDocumento, ErrorLLM, Perfil, Respuesta, combinar  # noqa: E402
from agentes.perfil.texto import alertas_inyeccion, evidencia_en_texto  # noqa: E402
from contrato.modelos import Habilidad  # noqa: E402

CARPETA = Path(__file__).resolve().parent
RUTA_RESULTADOS = CARPETA / "resultados.md"


def taxonomia() -> list[Habilidad]:
    datos = json.loads((RAIZ / "scripts" / "demo" / "datos_demo.json").read_text(encoding="utf-8"))
    return [Habilidad(**h) for h in datos["habilidades"]]


class LLMSimulado:
    """Devuelve las respuestas del caso en orden (la última se repite). Un dict es JSON, un texto
    es una transcripción y {"falla": ...} simula que el servicio no responde."""

    def __init__(self, respuestas: list):
        self.respuestas = list(respuestas)
        self.prompts: list[str] = []

    def _siguiente(self):
        r = self.respuestas.pop(0) if len(self.respuestas) > 1 else self.respuestas[0]
        if isinstance(r, dict) and "falla" in r:
            raise ErrorLLM(r["falla"])
        return r

    def json(self, sistema, usuario):
        self.prompts.append(usuario)
        return self._siguiente()

    def json_con_imagen(self, sistema, instruccion, imagen, tipo_mime):
        return self._siguiente()

    def transcribir(self, audio, nombre_archivo):
        return self._siguiente()


def _texto_de(entrada: dict) -> str:
    if "texto_repetido" in entrada:
        r = entrada["texto_repetido"]
        return r["frase"] * r["veces"]
    return entrada.get("texto", "")


def ejecutar_caso(caso: dict, cliente=None) -> dict:
    """Corre un caso y devuelve lo observado (sin juzgar)."""
    e = caso["entrada"]
    if cliente is None and e.get("llm") is not None:
        cliente = LLMSimulado(e["llm"])
    perfil = Perfil(taxonomia(), cliente)
    fuente, alertas_previas = "", []
    try:
        if e["tipo"] == "cv":
            fuente = _texto_de(e)
            r = perfil.desde_cv(fuente)
        elif e["tipo"] == "entrevista":
            fuente = " ".join(x["texto"] for x in e["respuestas"])
            r = perfil.desde_entrevista([Respuesta(**x) for x in e["respuestas"]])
        elif e["tipo"] == "pdf":
            fuente = perfil.texto_de_pdf(e["bytes_texto"].encode())
            r = perfil.desde_cv(fuente)
        elif e["tipo"] == "imagen":
            fuente = perfil.texto_de_imagen(e["bytes_texto"].encode(), e["tipo_mime"])
            r = perfil.desde_cv(fuente)
        elif e["tipo"] == "audio":
            fuente = perfil.texto_de_audio(b"0" * e["tamano"], e["tipo_mime"])
            alertas_previas = alertas_inyeccion(fuente)
            r = perfil.desde_entrevista([Respuesta(pregunta_id=e.get("pregunta_id", "negocio"), texto=fuente[:600])])
        else:
            raise ValueError(f"tipo de entrada desconocido: {e['tipo']}")
    except ErrorDocumento as err:
        return {"tipo": "error_controlado", "mensaje": str(err)}

    prompts = getattr(cliente, "prompts", [])
    return {
        "tipo": "habilidades",
        "codigos": sorted(h.codigo for h in r.habilidades),
        "niveles": {h.codigo: h.nivel for h in r.habilidades},
        "descartadas": sorted({d.codigo for d in r.descartadas}),
        "metodo": r.metodo,
        "alertas": bool(r.alertas or alertas_previas),
        "recortado": r.texto_recortado,
        "delimitador_intacto": all(p.count("</cv>") == 1 and p.rstrip().endswith("</cv>") for p in prompts),
        # Garantía central de Perfil: toda habilidad aceptada tiene su cita en el texto original.
        "evidencias_en_texto": all(evidencia_en_texto(h.evidencia or "", fuente) for h in r.habilidades),
    }


def juzgar(esperado: dict, obs: dict) -> tuple[bool, str]:
    if esperado["tipo"] == "error_controlado":
        if obs["tipo"] != "error_controlado":
            return False, f"se esperaba un error controlado y salió {obs.get('codigos')}"
        ok = esperado["contiene"].lower() in obs["mensaje"].lower()
        return ok, f"error controlado: «{obs['mensaje']}»"
    if obs["tipo"] != "habilidades":
        return False, f"error inesperado: {obs.get('mensaje')}"
    fallas = []
    if obs["codigos"] != sorted(esperado["codigos"]):
        fallas.append(f"códigos {obs['codigos']} ≠ {sorted(esperado['codigos'])}")
    for c, n in esperado.get("niveles", {}).items():
        if obs["niveles"].get(c) != n:
            fallas.append(f"nivel de {c} = {obs['niveles'].get(c)} (esperado {n})")
    faltan = set(esperado.get("descartadas", [])) - set(obs["descartadas"])
    if faltan:
        fallas.append(f"no se descartó {sorted(faltan)}")
    for clave in ("metodo", "alertas", "recortado", "delimitador_intacto"):
        if clave in esperado and obs[clave] != esperado[clave]:
            fallas.append(f"{clave} = {obs[clave]} (esperado {esperado[clave]})")
    if not obs["evidencias_en_texto"]:
        fallas.append("hay una habilidad aceptada sin cita en el texto")
    detalle = f"{obs['codigos'] or 'ninguna'}" + (f"; descartadas {obs['descartadas']}" if obs["descartadas"] else "")
    return not fallas, "; ".join(fallas) or detalle


def _normal(obs: dict) -> str:
    return json.dumps(obs, sort_keys=True, ensure_ascii=False)


def correr(casos: list[dict]) -> list[dict]:
    resultados = []
    for caso in casos:
        try:
            obs1, obs2 = ejecutar_caso(caso), ejecutar_caso(caso)
            ok, detalle = juzgar(caso["esperado"], obs1)
            determinista = _normal(obs1) == _normal(obs2)
            if not determinista:
                ok, detalle = False, detalle + "; NO determinista"
            resultados.append({**{k: caso[k] for k in ("id", "categoria", "naturaleza")}, "oro": caso.get("oro", False),
                               "solo_metrica": caso.get("solo_metrica", False),
                               "cumple": ok, "detalle": detalle, "observado": obs1, "esperado": caso["esperado"]})
        except Exception as err:  # un fallo inesperado no aborta la evaluación
            resultados.append({**{k: caso[k] for k in ("id", "categoria", "naturaleza")}, "oro": caso.get("oro", False),
                               "solo_metrica": caso.get("solo_metrica", False), "cumple": False, "detalle": f"ERROR: {type(err).__name__}: {err}", "observado": None,
                               "esperado": caso["esperado"], "error": True})
    return resultados


def precision_exhaustividad(pares: list[tuple[set, set]]) -> tuple[float | None, float | None]:
    vp = sum(len(esp & obs) for esp, obs in pares)
    fp = sum(len(obs - esp) for esp, obs in pares)
    fn = sum(len(esp - obs) for esp, obs in pares)
    return (vp / (vp + fp) if vp + fp else None), (vp / (vp + fn) if vp + fn else None)


def _pct(v) -> str:
    return "N/A" if v is None else f"{v * 100:.1f} %"


def en_vivo(casos: list[dict]) -> dict | None:
    """Los casos «oro» con el LLM real. Devuelve métricas o None si no hay clave."""
    try:
        from dotenv import load_dotenv
        load_dotenv(RAIZ / ".env")
    except ImportError:
        pass
    from agentes.perfil.llm import cliente_desde_entorno
    cliente = cliente_desde_entorno()
    if cliente is None:
        return None
    pares, evidencias, filas = [], [], []
    for caso in (c for c in casos if c.get("oro")):
        obs = ejecutar_caso(caso, cliente=cliente)
        esp = set(caso["esperado"]["codigos"])
        got = set(obs.get("codigos", []))
        pares.append((esp, got))
        evidencias.append(obs.get("evidencias_en_texto", True))
        filas.append((caso["id"], sorted(esp), sorted(got), obs.get("metodo")))
    p, r = precision_exhaustividad(pares)
    return {"modelo": getattr(cliente, "modelo", "?"), "precision": p, "exhaustividad": r,
            "evidencias": sum(evidencias), "total": len(evidencias), "filas": filas}


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        return ""


def reporte(resultados: list[dict], vivo: dict | None, se_pidio_vivo: bool) -> str:
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    commit = _git(["rev-parse", "--short", "HEAD"]) or "(sin git)"
    reglas = [r for r in resultados if not r["solo_metrica"]]
    cumplen = sum(r["cumple"] for r in reglas)
    estado = "SATISFACTORIA" if cumplen == len(reglas) else "NO SATISFACTORIA"
    def _pr(filas):
        return precision_exhaustividad([(set(r["esperado"]["codigos"]), set(r["observado"]["codigos"])) for r in filas])
    oro = [r for r in reglas if r["oro"] and r["observado"]]
    medicion = [r for r in resultados if r["solo_metrica"] and r["observado"]]
    p, rec = _pr(oro)
    pm, rm = _pr(medicion)
    con_habilidades = [r for r in resultados if r["observado"] and r["observado"]["tipo"] == "habilidades"]
    garantia = sum(r["observado"]["evidencias_en_texto"] for r in con_habilidades)
    guard = [r for r in resultados if r["categoria"] == "guardrails"]

    lineas = [
        "# Resultados de los evals del agente Perfil", "",
        f"- Estado de la corrida: **{estado}**",
        f"- Generado por `agentes/perfil/evals/correr.py`: {fecha}",
        f"- Commit: `{commit}` · Python {platform.python_version()} · sin red (LLM simulado o ausente)",
        f"- Casos de reglas: **{len(reglas)}** · cumplen: **{cumplen}** · casos de medición (no cuentan para el estado): **{len(medicion)}**", "",
        "Cada caso se corrió dos veces y se compararon las salidas para verificar que sea determinista.", "",
        "## Métricas", "",
        "| Métrica | Valor | Qué mide |", "|---|---|---|",
        f"| Precisión sin LLM, frases reales | {_pct(pm)} | En {len(medicion)} frases escritas sin pensar en las palabras clave: de lo que encontró el respaldo, cuánto era correcto |",
        f"| Exhaustividad sin LLM, frases reales | {_pct(rm)} | En esas frases: de lo que tenía que salir, cuánto encontró (lo que se pierde aquí lo cubre el LLM; ver modo en vivo) |",
        f"| Extracción en casos de reglas | {_pct(p)} / {_pct(rec)} | Precisión / exhaustividad en los {len(oro)} casos «oro» que fijan el comportamiento esperado |",
        f"| Garantía de evidencia | {garantia}/{len(con_habilidades)} casos | Toda habilidad aceptada tiene su cita en el texto original |",
        f"| Guardrails | {sum(r['cumple'] for r in guard)}/{len(guard)} | Inyección (texto y voz), delimitador, entradas vacías, enormes, dañadas o de formato no admitido |",
        "",
    ]
    if vivo:
        lineas += [
            f"## Modo en vivo ({vivo['modelo']}, {fecha})", "",
            "No cuenta para el estado de la corrida: un modelo de lenguaje no es determinista.", "",
            f"- Precisión: **{_pct(vivo['precision'])}** · Exhaustividad: **{_pct(vivo['exhaustividad'])}**",
            f"- Garantía de evidencia: **{vivo['evidencias']}/{vivo['total']}** casos (el código descarta toda cita que no esté en el texto)", "",
            "| id | esperado | obtenido | método |", "|---|---|---|---|",
            *[f"| {i} | {', '.join(e) or '—'} | {', '.join(o) or '—'} | {m} |" for i, e, o, m in vivo["filas"]], "",
        ]
    elif se_pidio_vivo:
        lineas += ["## Modo en vivo", "", "No se corrió: falta `GROQ_API_KEY` en `.env`.", ""]
    lineas += ["## Casos", "", "| id | categoría | naturaleza | resultado | detalle |", "|---|---|---|---|---|"]
    for r in resultados:
        res = ("acierta" if r["cumple"] else "no acierta") if r["solo_metrica"] else ("cumple" if r["cumple"] else "**NO CUMPLE**")
        lineas.append(f"| {r['id']} | {r['categoria']} | {r['naturaleza']} | {res} | {r['detalle']} |")
    lineas += ["", "## Alcance", "",
               "- Ejercita el agente directamente (sin API ni frontend); el endpoint `/perfil/transcribir` lo cubren las pruebas de `tests/test_perfil.py`.",
               "- Sin red, el LLM se simula con respuestas fijas (incluidas respuestas maliciosas o rotas) para medir la validación determinística del código; la calidad del modelo real se mide con `--en-vivo`.",
               "- La extracción «oro» sin LLM mide el respaldo por palabras clave, que es lo que usa el sistema cuando no hay servicio.", ""]
    return "\n".join(lineas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--en-vivo", action="store_true", help="además, mide los casos «oro» con el LLM real")
    args = ap.parse_args(argv)
    clave = os.environ.pop("GROQ_API_KEY", None)   # la corrida normal es sin red
    RUTA_RESULTADOS.write_text("# Resultados de los evals del agente Perfil\n\n- Estado: **EN CURSO / INCOMPLETA**\n",
                               encoding="utf-8")
    casos = json.loads((CARPETA / "casos.json").read_text(encoding="utf-8"))
    resultados = correr(casos)
    vivo = None
    if args.en_vivo:
        if clave:
            os.environ["GROQ_API_KEY"] = clave
        vivo = en_vivo(casos)
    RUTA_RESULTADOS.write_text(reporte(resultados, vivo, args.en_vivo), encoding="utf-8")
    fallan = [r for r in resultados if not r["cumple"] and not r["solo_metrica"]]
    reglas = [r for r in resultados if not r["solo_metrica"]]
    medicion = [r for r in resultados if r["solo_metrica"]]
    print(f"{len(reglas) - len(fallan)}/{len(reglas)} casos de reglas cumplen; medición: {sum(r['cumple'] for r in medicion)}/{len(medicion)} aciertos"
          + (f"; fallan: {[r['id'] for r in fallan]}" if fallan else ""))
    return 1 if fallan else 0


if __name__ == "__main__":
    raise SystemExit(main())
