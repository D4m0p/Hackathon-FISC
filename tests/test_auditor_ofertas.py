"""Pruebas del auditor de ofertas: casos positivos, negativos y ambiguos.

Positivo: debe marcarse. Negativo: no debe marcarse. Ambiguo: se marca por diseño
(no hay estado "pendiente de revisión" en el contrato) y requiere revisión humana.
"""
import json
from pathlib import Path

import pytest

from agentes.auditor import Auditor, detectar
from contrato.modelos import ResultadoAuditoria, Turno, Vacante

RAIZ = Path(__file__).resolve().parent.parent
DATOS_DEMO = json.loads((RAIZ / "scripts" / "demo" / "datos_demo.json").read_text(encoding="utf-8"))


def oferta(texto, id="v1", titulo="Puesto", **cambios):
    datos = dict(id=id, empresa_id="e1", titulo=titulo, corregimiento="bella_vista",
                 turnos={Turno.manana}, salario_mensual=650, texto_original=texto)
    datos.update(cambios)
    return Vacante(**datos)


def reglas(texto):
    return {h.regla for h in detectar(texto)}


# ---------- positivos: requisitos claramente problemáticos ----------

@pytest.mark.parametrize("texto, esperada", [
    ("Se busca recepcionista femenina.", "genero"),
    ("Se busca señorita para atención al público.", "genero"),
    ("Se requiere dama para la recepción.", "genero"),
    ("Vacante exclusiva para hombres.", "genero"),
    ("Se busca varón para bodega.", "genero"),
    ("Buscamos personal masculino.", "genero"),
    ("Requisito: buena presencia.", "buena_presencia"),
    ("Se busca recepcionista con excelente presentación.", "buena_presencia"),
    ("Debe proyectar buena imagen ante el cliente.", "buena_presencia"),
    ("Se valora presencia impecable.", "buena_presencia"),
    ("Adjunte su fotografía al formulario.", "foto_obligatoria"),
    ("Envíe su CV con foto tipo carné.", "foto_obligatoria"),
    ("Debe residir en Arraiján.", "residir_en"),
    ("Buscamos personas que vivan en la ciudad.", "residir_en"),
    ("Requisito: soltera y sin hijos.", "estado_civil"),
])
def test_positivos_se_detectan(texto, esperada):
    assert esperada in reglas(texto)


@pytest.mark.parametrize("texto", [
    "Buscamos menor de 25 años.",
    "Entre 18 a 25 años.",
    "Edad: 20-30 años.",
    "No mayor de 40 años.",
    "Se requiere mayor de 30 años.",
    "Hasta 35 años.",
    "De 25 a 40 años.",
])
def test_edad_positiva(texto):
    assert "edad" in reglas(texto)


# ---------- negativos: ofertas limpias o requisitos negados ----------

@pytest.mark.parametrize("texto", [
    "Se busca cajero con experiencia en manejo de caja. Lunes a viernes.",
    "No se requiere experiencia previa; damos capacitación.",
    "Se valorará buena redacción y trabajo en equipo.",
    "Buscamos personal con o sin experiencia para atención al cliente.",
    "Se ofrece transporte y alimentación.",
    "No es necesario adjuntar foto.",
    "Puede enviar su CV sin foto.",
    "No es requisito residir en Panamá.",
    "No importa su estado civil.",
    "No se exige buena presencia.",
    "Se requiere ser mayor de 18 años.",
    "Disponible para trabajar a partir de los 18 años.",
    "Trabajo para mayores de 18 años.",
    "Empresa de ropa masculina busca vendedor.",
    "Sección de moda femenina, atención al público.",
    "Sin distinción de género: damas y caballeros.",
    "Se pide entre 2 y 5 años de experiencia en ventas.",
    "Se valorará experiencia de 3 a 5 años.",
])
def test_negativos_no_se_marcan(texto):
    assert reglas(texto) == set()


# ---------- ambiguos: se marcan y requieren revisión humana ----------

@pytest.mark.parametrize("texto, regla", [
    ("Se requiere ser mayor de 21 años.", "edad"),
    ("Debe residir en Panamá.", "residir_en"),
    ("Se valorará buena presencia.", "buena_presencia"),
])
def test_ambiguos_se_marcan_para_revision_humana(texto, regla):
    assert regla in reglas(texto)


# ---------- coherencia con el contrato ----------

def test_rechazo_siempre_trae_hallazgos_con_detalle_y_sugerencia():
    textos = ["femenina", "menor de 30 años", "buena presencia", "adjunte su fotografía",
              "debe residir en Arraiján", "soltera"]
    for texto in textos:
        r = Auditor().auditar_oferta(oferta(texto))
        assert r.aprobado is False
        assert r.hallazgos, f"sin hallazgos para: {texto}"
        assert all(h.detalle and h.sugerencia for h in r.hallazgos)
        # un rechazo sin hallazgos sería inválido para el contrato
        ResultadoAuditoria(tipo=r.tipo, objeto_id=r.objeto_id, aprobado=r.aprobado,
                           hallazgos=r.hallazgos)


def test_fragmento_es_subcadena_del_texto_original():
    texto = "Se busca recepcionista femenina de buena presencia."
    for h in detectar(texto):
        assert h.fragmento and h.fragmento in texto


def test_deteccion_determinista():
    texto = "femenina, menor de 25 años, buena presencia, adjunte su fotografía"
    assert detectar(texto) == detectar(texto)


# ---------- integración básica ----------

def test_oferta_limpia_se_aprueba():
    r = Auditor().auditar_oferta(oferta("Se busca cajero con experiencia en manejo de caja."))
    assert r.aprobado is True and r.hallazgos == []


def test_detecta_senal_solo_en_el_titulo():
    v = oferta("Puesto de atención al cliente.", titulo="Recepcionista femenina")
    assert [h.regla for h in Auditor().auditar_oferta(v).hallazgos] == ["genero"]


def test_texto_vacio_no_genera_hallazgos():
    assert detectar("") == [] and detectar(None) == []


def test_la_oferta_v10_de_la_demo_se_bloquea():
    v10 = next(v for v in DATOS_DEMO["vacantes"] if v["id"] == "v10")
    r = Auditor().auditar_oferta(Vacante(**v10))
    assert r.aprobado is False
    assert {"genero", "edad", "buena_presencia"} <= {h.regla for h in r.hallazgos}


def test_auditar_matching_por_ahora_no_emite_resultados():
    assert Auditor().auditar_matching(None, [], {}, [], None) == []


# ---------- regresiones (revisión del 16-10) ----------

def _reglas_de(texto):
    return [h.regla for h in detectar(texto)]


def test_una_negacion_no_oculta_un_requisito_real_mas_adelante():
    assert "foto_obligatoria" in _reglas_de("No se requiere foto obligatoria. Enviar CV con foto al correo.")
    assert "residir_en" in _reglas_de("No es necesario residir en Arraiján, pero debe residir en La Chorrera.")


def test_negacion_sola_sigue_sin_marcarse():
    assert _reglas_de("No se requiere foto obligatoria.") == []


def test_no_aceptar_menores_de_edad_es_legal():
    assert _reglas_de("No se aceptan menores de 18 años.") == []
    assert _reglas_de("Abstenerse menores de 18 años.") == []


def test_un_tope_de_edad_adulta_se_sigue_marcando():
    assert _reglas_de("Solo menores de 25 años.") == ["edad"]
    assert _reglas_de("No mayor de 30 años.") == ["edad"]


def test_ni_continua_la_negacion():
    assert _reglas_de("No se exige buena presencia ni excelente presentación.") == []
    assert _reglas_de("No es requisito residir en Panamá ni vivir en la ciudad.") == []
    assert _reglas_de("No se pide fotografía obligatoria ni foto reciente.") == []


def test_la_negacion_se_reconoce_por_palabra_completa():
    # "mini" termina en "ni" y "Calvin" en "in": no son negaciones
    assert "foto_obligatoria" in _reglas_de("Tienda mini con foto obligatoria.")
