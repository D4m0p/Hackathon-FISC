"""Concurrencia: un aviso lento no frena al sistema, y la decisión del orientador es
atómica en la base aunque haya varios procesos (cada uno con su propio candado)."""
import threading
import time
from datetime import datetime, timezone

from contrato.modelos import DatosPersonales, Traslado
from orquestador import Almacen, ErrorDeFlujo, Orquestador
from tests.test_orquestador import AuditorFalso, MercadoFalso, joven, vacante

VIERNES = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)


class NotificadorLento:
    def __init__(self, segundos):
        self.segundos, self.enviados = segundos, []

    def enviar(self, destino, texto):
        time.sleep(self.segundos)
        self.enviados.append(texto)
        return True


class NotificadorRoto:
    def enviar(self, destino, texto):
        raise ConnectionError("Telegram caído")


def preparar(o):
    o.almacen.guardar_traslados([Traslado(origen="la_chorrera", destino="arraijan", minutos=30, costo=1.0)])
    o.registrar_joven(joven("j1"), DatosPersonales(joven_id="j1", nombre="Ana", contacto_telegram="1"))
    o.registrar_joven(joven("j2"))
    o.publicar_vacante(vacante("v1"))
    o.deslizar("joven", "j1", "v1", True)
    o.deslizar("empresa", "j1", "v1", True)
    o.ejecutar_matching()


def test_un_aviso_lento_no_bloquea_a_los_demas():
    notificador = NotificadorLento(1.0)
    o = Orquestador(Almacen(), mercado=MercadoFalso(), auditor=AuditorFalso(),
                    notificador=notificador, reloj=lambda: VIERNES)
    preparar(o)
    hilo = threading.Thread(target=o.orientador_decidir, args=("j1", "v1", True))
    hilo.start()
    time.sleep(0.2)                                   # la aprobación ya está enviando el aviso
    t0 = time.perf_counter()
    o.deslizar("joven", "j2", "v1", True)             # otra operación que necesita el candado
    espera = time.perf_counter() - t0
    hilo.join()
    assert espera < 0.5, f"deslizar esperó {espera:.2f} s al aviso lento"
    assert len(notificador.enviados) == 1
    assert o.almacen.mensajes()[0]["enviado"] is True
    assert "agendar_y_notificar" in [t.accion for t in o.almacen.trazas("orquestador")]


def test_un_canal_caido_no_deshace_la_aprobacion():
    o = Orquestador(Almacen(), mercado=MercadoFalso(), auditor=AuditorFalso(),
                    notificador=NotificadorRoto(), reloj=lambda: VIERNES)
    preparar(o)
    a = o.orientador_decidir("j1", "v1", aprobar=True)
    assert a.aprobada is True
    assert o.almacen.mensajes()[0]["enviado"] is False


def test_dos_procesos_no_pueden_aprobar_la_misma_asignacion(tmp_path):
    ruta = str(tmp_path / "compartida.db")
    lento = lambda: (time.sleep(0.2), VIERNES)[1]    # noqa: E731 — ensancha la carrera
    procesos = [Orquestador(Almacen(ruta), mercado=MercadoFalso(), auditor=AuditorFalso(),
                            notificador=NotificadorLento(0), reloj=lento) for _ in range(2)]
    preparar(procesos[0])
    resultados = []

    def decidir(o):
        try:
            o.orientador_decidir("j1", "v1", aprobar=True)
            resultados.append("ok")
        except ErrorDeFlujo:
            resultados.append("ya decidida")

    hilos = [threading.Thread(target=decidir, args=(o,)) for o in procesos]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(resultados) == ["ok", "ya decidida"]
    assert len(Almacen(ruta).mensajes()) == 1
