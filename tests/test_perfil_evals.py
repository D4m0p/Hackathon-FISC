import json
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent.parent / "agentes" / "perfil" / "evals"
sys.path.insert(0, str(CARPETA))
import correr  # noqa: E402


def casos():
    return json.loads((CARPETA / "casos.json").read_text(encoding="utf-8"))


def test_todos_los_casos_de_reglas_cumplen_y_son_deterministas():
    resultados = correr.correr(casos())
    fallan = [(r["id"], r["detalle"]) for r in resultados if not r["cumple"] and not r["solo_metrica"]]
    assert not fallan


def test_el_arnes_detecta_expectativas_equivocadas():
    malos = []
    for c in casos():
        e = c["esperado"]
        if e["tipo"] == "habilidades":
            e["codigos"] = sorted(set(e["codigos"]) ^ {"ventas"})
        else:
            e["contiene"] = "mensaje que no existe"
        malos.append(c)
    assert not any(r["cumple"] for r in correr.correr(malos))


def test_toda_habilidad_aceptada_tiene_su_cita():
    for r in correr.correr(casos()):
        if r["observado"] and r["observado"]["tipo"] == "habilidades":
            assert r["observado"]["evidencias_en_texto"], r["id"]
