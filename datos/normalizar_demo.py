"""Convierte los datos de investigación de `datos/*.csv` en datos de MUESTRA
compatibles con los modelos `Vacante` y `Curso` del contrato.

Regla de oro: no se inventa nada. Un registro solo se convierte si TODOS los
campos obligatorios del modelo existen en la fuente. Si falta alguno, el registro
se excluye y queda registrado el motivo en `datos/demo/exclusiones.json`. No se
rellenan campos por conveniencia (ni con valores por defecto del modelo).

Los originales (`datos/ofertas_empleo.csv`, `datos/cursos.csv`) NO se tocan.

Uso (desde la raíz del repo):
    python3 datos/normalizar_demo.py                 # escribe en datos/demo/
    python3 datos/normalizar_demo.py --salida /tmp/d  # escribe en otra carpeta

La salida es determinística: mismos CSV de entrada -> mismos bytes de salida.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA_OFERTAS = RAIZ / "datos" / "ofertas_empleo.csv"
ENTRADA_CURSOS = RAIZ / "datos" / "cursos.csv"
SALIDA = RAIZ / "datos" / "demo"

NOTA = ("Muestras de investigación, NO oportunidades activas confirmadas. Cada registro "
        "proviene de un portal público (ver 'origen') y se conserva solo como ejemplo.")

# Campos obligatorios de cada modelo (según `contrato/modelos.py`). El resto tiene
# valor por defecto en el modelo y por eso no bloquea la conversión.
REQ_VACANTE = ["id", "empresa_id", "titulo", "corregimiento", "turnos", "salario_mensual"]
REQ_CURSO = ["id", "centro", "nombre", "corregimiento", "turnos",
             "sesiones_por_semana", "semanas", "cupos_disponibles", "habilidades_otorgadas"]

# Por qué no se pudo tomar cada campo obligatorio desde la fuente.
EXPLICACION = {
    "empresa_id": "la fuente da el nombre de la empresa, no un identificador",
    "corregimiento": "la fuente da provincia/ubicación textual, no un corregimiento",
    "turnos": "la fuente da jornada textual ('Tiempo completo'), no los turnos del enum",
    "salario_mensual": "la fuente da texto o un rango, no un monto mensual numérico",
    "sesiones_por_semana": "vacío en la fuente",
    "semanas": "vacío en la fuente",
    "cupos_disponibles": "vacío en la fuente",
    "habilidades_otorgadas": "la fuente lista códigos sin nivel y el modelo exige nivel 1-3",
}


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _numero(valor: str):
    """Devuelve float si el texto es un número puro; None en cualquier otro caso."""
    texto = (valor or "").strip()
    if not texto:
        return None
    try:
        return float(texto.replace(",", ""))
    except ValueError:
        return None


def convertir_oferta(row: dict) -> tuple[dict | None, dict | None]:
    """(registro Vacante, motivo_exclusion). Exactamente uno es None."""
    faltan = []
    if not row["id"].strip():
        faltan.append("id")
    if not row["titulo_original"].strip():
        faltan.append("titulo")
    # Campos obligatorios que la fuente no permite mapear de forma fiel:
    if not _es_id(row.get("empresa", "")):
        faltan.append("empresa_id")
    if not _es_corregimiento(row.get("provincia", "")):
        faltan.append("corregimiento")
    if not _turnos(row.get("jornada", "")):
        faltan.append("turnos")
    if _numero_mensual(row.get("salario", "")) is None:
        faltan.append("salario_mensual")

    origen = {"archivo": "datos/ofertas_empleo.csv", "id_origen": row["id"], "url": row["url"]}
    if faltan:
        return None, _exclusion("oferta", origen, faltan,
                                mapeados=["id", "titulo", "texto_original"])
    return {
        "id": row["id"],
        "empresa_id": _es_id(row["empresa"]),
        "titulo": row["titulo_original"],
        "corregimiento": _es_corregimiento(row["provincia"]),
        "turnos": _turnos(row["jornada"]),
        "salario_mensual": _numero_mensual(row["salario"]),
        "texto_original": row["requisitos_originales"] or None,
    }, None


def convertir_curso(row: dict) -> tuple[dict | None, dict | None]:
    """(registro Curso, motivo_exclusion). Exactamente uno es None."""
    faltan = []
    if not row["id"].strip():
        faltan.append("id")
    if not row["proveedor"].strip():
        faltan.append("centro")
    if not row["nombre"].strip():
        faltan.append("nombre")
    if not _es_corregimiento(row.get("corregimiento", "")):
        faltan.append("corregimiento")
    if not _turnos(row.get("turnos", "")):
        faltan.append("turnos")
    if _entero(row.get("sesiones_por_semana", "")) is None:
        faltan.append("sesiones_por_semana")
    if _entero(row.get("semanas", "")) is None:
        faltan.append("semanas")
    if _entero(row.get("cupos_disponibles", "")) is None:
        faltan.append("cupos_disponibles")
    if not _habilidades_con_nivel(row.get("habilidades_otorgadas", "")):
        faltan.append("habilidades_otorgadas")

    origen = {"archivo": "datos/cursos.csv", "id_origen": row["id"], "url": row["url"]}
    if faltan:
        return None, _exclusion("curso", origen, faltan,
                                mapeados=["id", "centro", "nombre", "costo"])
    return {
        "id": row["id"],
        "centro": row["proveedor"],
        "nombre": row["nombre"],
        "corregimiento": _es_corregimiento(row["corregimiento"]),
        "turnos": _turnos(row["turnos"]),
        "sesiones_por_semana": _entero(row["sesiones_por_semana"]),
        "semanas": _entero(row["semanas"]),
        "costo": _numero(row["costo"]) or 0,
        "cupos_disponibles": _entero(row["cupos_disponibles"]),
        "habilidades_otorgadas": _habilidades_con_nivel(row["habilidades_otorgadas"]),
    }, None


# --- Mapeadores: devuelven None cuando la fuente no permite representar el campo ---

def _es_id(valor: str):
    """El modelo exige un identificador (patrón ^[A-Za-z0-9_.-]+$). Un nombre de
    empresa no lo es; por eso este mapeador siempre devuelve None."""
    return None


def _es_corregimiento(valor: str):
    """La fuente no trae un corregimiento (solo provincia/ubicación textual)."""
    return None


def _turnos(valor: str):
    """'Tiempo completo' no es ninguno de los turnos del enum."""
    return None


def _numero_mensual(valor: str):
    """El salario viene como texto o rango y sin periodo confirmado."""
    return None


def _entero(valor: str):
    texto = (valor or "").strip()
    return int(texto) if texto.isdigit() else None


def _habilidades_con_nivel(valor: str):
    """La taxonomía exige nivel (1-3) y la fuente solo lista códigos: no se
    puede fijar el nivel sin inventarlo."""
    return None


def _exclusion(tipo: str, origen: dict, faltan: list[str], mapeados: list[str]) -> dict:
    detalle = "; ".join(f"{c} ({EXPLICACION.get(c, 'ausente en la fuente')})" for c in faltan)
    return {
        "tipo": tipo,
        "origen": origen,
        "campos_mapeados": mapeados,
        "campos_faltantes": faltan,
        "motivo": f"No se convierte a {('Vacante' if tipo == 'oferta' else 'Curso')}: faltan campos "
                  f"obligatorios -> {detalle}.",
    }


def _fecha_datos(filas: list[dict]) -> str:
    fechas = sorted({r.get("fecha_consulta", "").strip() for r in filas if r.get("fecha_consulta")})
    return fechas[-1] if fechas else ""


def _escribir(ruta: Path, obj: dict) -> None:
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def convertir(salida: Path) -> dict:
    ofertas = _leer_csv(ENTRADA_OFERTAS)
    cursos = _leer_csv(ENTRADA_CURSOS)
    salida.mkdir(parents=True, exist_ok=True)
    fecha = _fecha_datos(ofertas + cursos)

    vacantes, exc_ofertas = [], []
    for row in sorted(ofertas, key=lambda r: r["id"]):
        modelo, excl = convertir_oferta(row)
        (vacantes if modelo else exc_ofertas).append(modelo or excl)

    cursos_ok, exc_cursos = [], []
    for row in sorted(cursos, key=lambda r: r["id"]):
        modelo, excl = convertir_curso(row)
        (cursos_ok if modelo else exc_cursos).append(modelo or excl)

    _escribir(salida / "vacantes_demo.json", {
        "_nota": NOTA,
        "_advertencia": "Los registros de 'registros' validan contra contrato.modelos.Vacante.",
        "fecha_datos": fecha,
        "origen": {"archivo": "datos/ofertas_empleo.csv", "sha256": sha256(ENTRADA_OFERTAS)},
        "total_origen": len(ofertas), "total_convertidos": len(vacantes),
        "total_excluidos": len(exc_ofertas), "registros": vacantes,
    })
    _escribir(salida / "cursos_demo.json", {
        "_nota": NOTA,
        "_advertencia": "Los registros de 'registros' validan contra contrato.modelos.Curso.",
        "fecha_datos": fecha,
        "origen": {"archivo": "datos/cursos.csv", "sha256": sha256(ENTRADA_CURSOS)},
        "total_origen": len(cursos), "total_convertidos": len(cursos_ok),
        "total_excluidos": len(exc_cursos), "registros": cursos_ok,
    })
    _escribir(salida / "exclusiones.json", {
        "_nota": "Trazabilidad: cada registro excluido enlaza con su origen y explica qué "
                 "campos obligatorios del modelo faltan y por qué no se tomaron de la fuente.",
        "fecha_datos": fecha, "ofertas": exc_ofertas, "cursos": exc_cursos,
    })
    return {"ofertas_origen": len(ofertas), "ofertas_convertidas": len(vacantes),
            "cursos_origen": len(cursos), "cursos_convertidos": len(cursos_ok)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--salida", default=str(SALIDA))
    args = p.parse_args()
    resumen = convertir(Path(args.salida))
    print(f"Salida: {args.salida}")
    for k, v in resumen.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
