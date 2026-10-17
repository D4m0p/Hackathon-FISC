"""Consultas puntuales del almacén (optimización): deben dar lo mismo que filtrar todo."""
from contrato.modelos import Asignacion, Desglose, Traslado
from orquestador import Almacen


def asignacion(j, v, aprobada=None):
    return Asignacion(joven_id=j, vacante_id=v, aprobada=aprobada,
                      desglose=Desglose(habilidades=1, traslado=1, salario=1, total=1))


def test_asignaciones_filtradas_no_confunden_ids_parecidos():
    a = Almacen()
    for j, v in [("j1", "v1"), ("j1", "v10"), ("j10", "v1"), ("j10", "v10"), ("xj1", "v1"), ("j1", "xv1")]:
        a.guardar(asignacion(j, v))
    pares = lambda xs: sorted((x.joven_id, x.vacante_id) for x in xs)  # noqa: E731
    assert pares(a.asignaciones(joven_id="j1")) == [("j1", "v1"), ("j1", "v10"), ("j1", "xv1")]
    assert pares(a.asignaciones(vacante_id="v1")) == [("j1", "v1"), ("j10", "v1"), ("xj1", "v1")]
    assert pares(a.asignaciones(joven_id="j1", vacante_id="v1")) == [("j1", "v1")]
    assert len(a.asignaciones()) == 6


def test_filtrar_da_lo_mismo_que_listar_todo():
    a = Almacen()
    for i in range(12):
        a.guardar(asignacion(f"j{i % 4}", f"v{i % 3}"))
    for j in ("j0", "j1", "j3"):
        assert a.asignaciones(joven_id=j) == [x for x in a.listar(Asignacion) if x.joven_id == j]


def test_interes_mutuo_puntual():
    a = Almacen()
    a.deslizar("joven", "j1", "v1", True)
    assert not a.hay_interes_mutuo("j1", "v1")
    a.deslizar("empresa", "j1", "v1", True)
    assert a.hay_interes_mutuo("j1", "v1")
    a.deslizar("empresa", "j1", "v1", False)
    assert not a.hay_interes_mutuo("j1", "v1")
    assert a.hay_interes_mutuo("j1", "v1") == (("j1", "v1") in a.interes_mutuo())


def test_deslizados_en_una_consulta():
    a = Almacen()
    a.deslizar("joven", "j1", "v1", False)
    a.deslizar("joven", "j1", "v2", True)
    a.deslizar("empresa", "j2", "v1", True)
    assert a.deslizadas_por_joven("j1") == {"v1", "v2"}
    assert a.deslizados_por_empresa("v1") == {"j2"}
    assert a.deslizadas_por_joven("j2") == set()


def test_cache_de_traslados_se_invalida_al_guardar():
    a = Almacen()
    a.guardar_traslados([Traslado(origen="a", destino="b", minutos=10, costo=1)])
    assert [t.minutos for t in a.traslados()] == [10]
    a.guardar_traslados([Traslado(origen="a", destino="b", minutos=99, costo=1)])
    assert [t.minutos for t in a.traslados()] == [99]
    a.traslados().clear()                                   # la copia no rompe la caché
    assert len(a.traslados()) == 1


def test_base_en_disco_usa_wal(tmp_path):
    import sqlite3
    ruta = str(tmp_path / "x.db")
    Almacen(ruta)
    assert sqlite3.connect(ruta).execute("PRAGMA journal_mode").fetchone()[0] == "wal"
