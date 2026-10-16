"""La demo depende de esta historia: si alguien cambia los datos, estas pruebas avisan."""
import json
import sys
from pathlib import Path

from contrato.modelos import Hallazgo, ResultadoAuditoria
from orquestador import Almacen, Orquestador

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from semilla_demo import DATOS, cargar  # noqa: E402

datos = json.loads(DATOS.read_text(encoding="utf-8"))


class AuditorQueBloqueaPresencia:
    def auditar_oferta(self, v):
        if "buena presencia" in (v.texto_original or ""):
            return ResultadoAuditoria(tipo="oferta", objeto_id=v.id, aprobado=False, hallazgos=[
                Hallazgo(regla="buena_presencia", detalle="Requisito de apariencia física")])
        return ResultadoAuditoria(tipo="oferta", objeto_id=v.id, aprobado=True)

    def auditar_matching(self, *args):
        return []


def test_la_demo_produce_la_historia_esperada():
    orq = Orquestador(Almacen())
    r = cargar(orq, datos, con_matching=True)
    assert r["interes_mutuo"] == 5
    assert r["asignaciones"] == ["j01→v01", "j03→v02", "j04→v06", "j06→v03", "j10→v01"]
    assert r["planes"] == ["j07", "j08"]
    assert orq.plan_de("j08").cursos == ["c01"]      # sin CV → curso de ventas cerca de casa


def test_tocumen_no_aparece_para_quien_vive_en_la_chorrera():
    orq = Orquestador(Almacen())
    cargar(orq, datos)
    orq.almacen.deslizar("joven", "j01", "v01", False)   # que no se esconda por ya deslizada
    assert "v03" not in [v.id for v, _ in orq.tarjetas_joven("j01")]


def test_la_oferta_discriminatoria_se_bloquea_con_un_auditor_real():
    orq = Orquestador(Almacen(), auditor=AuditorQueBloqueaPresencia())
    assert cargar(orq, datos)["bloqueadas"] == ["v10"]


def test_los_datos_son_validos_y_marcados_como_ilustrativos():
    assert "ILUSTRATIVOS" in datos["_nota"]
    codigos = {h["codigo"] for h in datos["habilidades"]}
    usados = {r["codigo"] for v in datos["vacantes"] for r in v["habilidades_requeridas"]}
    usados |= {h["codigo"] for j in datos["jovenes"] for h in j["joven"]["habilidades"]}
    usados |= {h["codigo"] for c in datos["cursos"] for h in c["habilidades_otorgadas"]}
    assert usados <= codigos, f"habilidades sin nombre en el catálogo: {usados - codigos}"
