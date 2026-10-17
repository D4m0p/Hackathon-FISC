"""Comparacion esperado/obtenido y metricas agregadas de los evals.

No conoce el comportamiento real: solo decide si una observacion cumple la
expectativa declarada del caso y agrega resultados. Las metricas se calculan
solo con los casos realmente ejecutados; si no hay ejemplos, devuelven None
(se reporta como N/A).
"""
from __future__ import annotations

from collections import defaultdict


def comparar(caso: dict, obs: dict) -> tuple[bool, str]:
    esperado = caso["esperado"]
    tipo = esperado["tipo"]

    if tipo == "error_controlado":
        return _comparar_error_controlado(esperado, obs)

    comparadores = {
        "matching": _comparar_matching,
        "detector": _comparar_detector,
        "contrafactual": _comparar_contrafactual,
        "mercado": _comparar_mercado,
    }
    comparador = comparadores.get(caso["asunto"])
    if comparador is None:
        return False, f"asunto desconocido: {caso['asunto']}"
    return comparador(esperado, obs, caso)


def _comparar_error_controlado(esperado, obs):
    if obs.get("tipo") != "error_controlado":
        return False, f"se esperaba un error controlado y se obtuvo {obs.get('tipo')}"
    if "excepcion" in esperado and obs.get("excepcion") != esperado["excepcion"]:
        return False, f"excepcion {obs.get('excepcion')} != {esperado['excepcion']}"
    if "campos" in esperado:
        faltan = set(esperado["campos"]) - set(obs.get("campos", []))
        if faltan:
            return False, f"campos esperados ausentes: {sorted(faltan)} (vistos {obs.get('campos')})"
    return True, "error controlado como se esperaba"


def _comparar_matching(esperado, obs, caso):
    if obs.get("tipo") != "asignacion":
        return False, f"no hubo asignacion: {obs}"
    if esperado["tipo"] == "asignacion_exacta":
        pares = sorted([p[0], p[1]] for p in esperado["asignaciones"])
        if sorted(obs["asignaciones"]) != pares:
            return False, f"asignaciones {obs['asignaciones']} != {pares}"
        if "sin_asignar" in esperado and sorted(obs["sin_asignar"]) != sorted(esperado["sin_asignar"]):
            return False, f"sin_asignar {obs['sin_asignar']} != {esperado['sin_asignar']}"
        return True, "asignacion esperada"
    if esperado["tipo"] == "sin_asignacion":
        if obs["asignaciones"]:
            return False, f"se esperaba ninguna asignacion, hubo {obs['asignaciones']}"
        jovenes = sorted(j["id"] for j in caso["entrada"]["jovenes"])
        if sorted(obs["sin_asignar"]) != jovenes:
            return False, f"sin_asignar {obs['sin_asignar']} != {jovenes}"
        return True, "sin asignacion, como se esperaba"
    if esperado["tipo"] == "propiedades":
        problemas = []
        if obs["asignaciones_infactibles"]:
            problemas.append(f"{obs['asignaciones_infactibles']} asignaciones infactibles")
        if obs["violaciones_cupos"]:
            problemas.append(f"{obs['violaciones_cupos']} violaciones de cupos")
        if obs["incompatibles"]:
            problemas.append(f"{obs['incompatibles']} asignaciones incompatibles con habilidades")
        if "asignaciones" in esperado and len(obs["asignaciones"]) != esperado["asignaciones"]:
            problemas.append(f"asignaciones={len(obs['asignaciones'])} != {esperado['asignaciones']}")
        if "sin_asignar_cantidad" in esperado and len(obs["sin_asignar"]) != esperado["sin_asignar_cantidad"]:
            problemas.append(f"sin_asignar={len(obs['sin_asignar'])} != {esperado['sin_asignar_cantidad']}")
        return (False, "; ".join(problemas)) if problemas else (True, "propiedades respetadas")
    return False, f"tipo de matching no soportado: {esperado['tipo']}"


def _comparar_detector(esperado, obs, caso=None):
    if obs.get("tipo") != "oferta":
        return False, f"no hubo auditoria: {obs}"
    if esperado["tipo"] == "aprueba":
        return (True, "aprobada") if obs["aprobado"] else (False, f"se esperaba aprobada, reglas {obs['reglas']}")
    if esperado["tipo"] == "bloquea":
        if obs["aprobado"]:
            return False, "se esperaba bloqueada y se aprobo"
        faltan = set(esperado.get("reglas", [])) - set(obs["reglas"])
        if faltan:
            return False, f"no se detectaron las reglas {sorted(faltan)}; detectadas {obs['reglas']}"
        return True, f"bloqueada por {obs['reglas']}"
    return False, f"tipo de detector no soportado: {esperado['tipo']}"


def _comparar_contrafactual(esperado, obs, caso=None):
    if obs.get("tipo") != "hallazgos":
        return False, f"salida inesperada: {obs}"
    reglas = {r for _, r in obs["hallazgos"]}
    if esperado["tipo"] == "sin_hallazgo":
        if obs["hallazgos"]:
            return False, f"hallazgos inesperados: {obs['hallazgos']}"
        if not obs["aprobado"]:
            return False, "se esperaba aprobado y sin hallazgos"
        if obs.get("igual_datos") is False:
            return False, "cambiar nombre/genero altero el resultado"
        return True, "sin hallazgos"
    if esperado["tipo"] == "hallazgo":
        objetivo = set(esperado.get("reglas", []))
        if not (objetivo & reglas):
            return False, f"no se detecto {sorted(objetivo)}; hallazgos {sorted(reglas)}"
        return True, f"detectado {sorted(objetivo & reglas)}"
    return False, f"tipo de contrafactual no soportado: {esperado['tipo']}"


def _comparar_mercado(esperado, obs, caso=None):
    if esperado["tipo"] != "vacante":
        return False, f"tipo de mercado no soportado: {esperado['tipo']}"
    if obs.get("tipo") != "vacante":
        return False, f"se esperaba vacante y se obtuvo {obs.get('tipo')}"
    if "codigos" in esperado and sorted(obs["codigos"]) != sorted(esperado["codigos"]):
        return False, f"codigos {obs['codigos']} != {esperado['codigos']}"
    if "corregimiento" in esperado and obs["corregimiento"] != esperado["corregimiento"]:
        return False, f"corregimiento {obs['corregimiento']} != {esperado['corregimiento']}"
    if "turnos" in esperado and sorted(obs["turnos"]) != sorted(esperado["turnos"]):
        return False, f"turnos {obs['turnos']} != {esperado['turnos']}"
    return True, "vacante esperada"


def _conteo(resultados, clave):
    agregado: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "cumplido": 0})
    for r in resultados:
        agregado[r[clave]]["total"] += 1
        agregado[r[clave]]["cumplido"] += int(r["cumplido"])
    return dict(sorted(agregado.items()))


def resumen(resultados: list[dict]) -> dict:
    obs_matching = [r["obs"] for r in resultados
                    if r["asunto"] == "matching" and r["obs"].get("tipo") == "asignacion"]
    total_asignaciones = sum(len(o["asignaciones"]) for o in obs_matching)
    asignaciones_infactibles = sum(o["asignaciones_infactibles"] for o in obs_matching)
    violaciones_cupos = sum(o["violaciones_cupos"] for o in obs_matching)
    incompatibles = sum(o["incompatibles"] for o in obs_matching)

    tp = fp = fn = tn = 0
    for r in resultados:
        if r["asunto"] != "detector" or r["obs"].get("tipo") != "oferta":
            continue
        etiqueta = r.get("etiqueta")
        bloqueado = not r["obs"]["aprobado"]
        if etiqueta == "discriminatoria":
            tp += int(bloqueado)
            fn += int(not bloqueado)
        elif etiqueta == "limpia":
            fp += int(bloqueado)
            tn += int(not bloqueado)

    tp_s = fp_s = fn_s = 0
    for r in resultados:
        if r["asunto"] != "mercado" or r["categoria"] != "mercado":
            continue
        if r["esperado"].get("tipo") != "vacante":
            continue
        if "codigos" not in r["esperado"] or r["obs"].get("tipo") != "vacante":
            continue
        esperados = set(r["esperado"]["codigos"])
        obtenidos = set(r["obs"]["codigos"])
        tp_s += len(esperados & obtenidos)
        fp_s += len(obtenidos - esperados)
        fn_s += len(esperados - obtenidos)

    contrafactual = [r for r in resultados if r["asunto"] == "contrafactual"]
    guardrails = [r for r in resultados if r["categoria"] == "guardrails"]
    malformadas = [r for r in resultados if r["categoria"] == "malformadas"]

    return {
        "por_categoria": _conteo(resultados, "categoria"),
        "por_asunto": _conteo(resultados, "asunto"),
        "matching": {
            "asignaciones": total_asignaciones,
            "asignaciones_infactibles": asignaciones_infactibles,
            "violaciones_cupos": violaciones_cupos,
            "incompatibles": incompatibles,
            "factibilidad": (1 - asignaciones_infactibles / total_asignaciones
                             if total_asignaciones else None),
        },
        "detector": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                     "precision": (tp / (tp + fp)) if (tp + fp) else None,
                     "exhaustividad": (tp / (tp + fn)) if (tp + fn) else None},
        "mercado": {"precision": (tp_s / (tp_s + fp_s)) if (tp_s + fp_s) else None,
                    "exhaustividad": (tp_s / (tp_s + fn_s)) if (tp_s + fn_s) else None},
        "contrafactuales": {"total": len(contrafactual),
                            "cumplido": sum(int(r["cumplido"]) for r in contrafactual)},
        "guardrails": {"total": len(guardrails),
                       "cumplido": sum(int(r["cumplido"]) for r in guardrails)},
        "malformadas": {"total": len(malformadas),
                        "cumplido": sum(int(r["cumplido"]) for r in malformadas)},
        "no_deterministas": sorted(r["id"] for r in resultados if not r["determinista"]),
    }