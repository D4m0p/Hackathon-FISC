"""Telegram: un bot no puede escribir a un "@usuario"; en la demo el aviso va al chat del equipo."""
import httpx
import pytest

from orquestador.notificador import NotificadorRegistro, NotificadorTelegram, desde_entorno


class Respuesta:
    def __init__(self, estado, cuerpo):
        self.status_code, self._cuerpo = estado, cuerpo

    def json(self):
        if isinstance(self._cuerpo, Exception):
            raise self._cuerpo
        return self._cuerpo


@pytest.fixture
def telegram(monkeypatch):
    """Simula la API de Telegram: solo acepta chats numéricos. Anota cada envío."""
    envios = []

    def post(url, json, timeout):
        envios.append(json)
        if str(json["chat_id"]).lstrip("-").isdigit():
            return Respuesta(200, {"ok": True})
        return Respuesta(400, {"ok": False, "description": "chat not found"})

    monkeypatch.setattr(httpx, "post", post)
    return envios


def test_chat_numerico_se_envia_directo(telegram):
    assert NotificadorTelegram("t", "999").enviar("12345", "Hola") is True
    assert [e["chat_id"] for e in telegram] == ["12345"]


def test_usuario_que_no_sirve_cae_al_chat_de_la_demo(telegram):
    assert NotificadorTelegram("t", "999").enviar("@maria", "Tiene entrevista") is True
    assert telegram[-1] == {"chat_id": "999", "text": "(Aviso para @maria) Tiene entrevista"}


def test_sin_destino_va_al_chat_de_la_demo(telegram):
    assert NotificadorTelegram("t", "999").enviar(None, "Hola") is True
    assert telegram[-1]["text"] == "Hola"


def test_sin_chat_de_demo_un_destino_invalido_no_se_envia(telegram):
    assert NotificadorTelegram("t", None).enviar("@maria", "Hola") is False
    assert NotificadorTelegram("t", None).enviar(None, "Hola") is False


def test_telegram_caido_o_respuesta_rara_no_rompe(monkeypatch):
    def caido(url, json, timeout):
        raise httpx.ConnectError("sin red")
    monkeypatch.setattr(httpx, "post", caido)
    assert NotificadorTelegram("t", "999").enviar("123", "x") is False
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: Respuesta(502, ValueError("no es JSON")))
    assert NotificadorTelegram("t", "999").enviar("123", "x") is False


def test_desde_entorno(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert isinstance(desde_entorno(), NotificadorRegistro)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    assert isinstance(desde_entorno(), NotificadorTelegram)
