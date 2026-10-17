"""Envío de mensajes. Telegram si hay token; si no, solo queda registrado."""
from __future__ import annotations

import os

import httpx


class NotificadorRegistro:
    """No envía nada; el orquestador igual guarda el mensaje en la base."""

    def enviar(self, destino: str | None, texto: str) -> bool:
        return False


class NotificadorTelegram:
    """Envía por la API de bots de Telegram.

    Un bot solo puede escribirle a quien ya le habló, y por su id numérico de chat (no por
    "@usuario"). Si el envío al joven falla y hay un chat de demostración configurado, el
    aviso va a ese chat indicando para quién era: así, en la demo, el mensaje se ve llegar.
    """

    def __init__(self, token: str, chat_por_defecto: str | None = None, timeout: float = 10):
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_por_defecto = chat_por_defecto
        self._timeout = timeout

    def _enviar_a(self, chat: str, texto: str) -> bool:
        try:
            r = httpx.post(self._url, json={"chat_id": chat, "text": texto}, timeout=self._timeout)
            return r.status_code == 200 and bool(r.json().get("ok", False))
        except (httpx.HTTPError, ValueError):   # sin red, Telegram caído o respuesta no JSON
            return False

    def enviar(self, destino: str | None, texto: str) -> bool:
        if destino and self._enviar_a(destino, texto):
            return True
        if not self._chat_por_defecto or destino == self._chat_por_defecto:
            return False
        prefijo = f"(Aviso para {destino}) " if destino else ""
        return self._enviar_a(self._chat_por_defecto, prefijo + texto)


def desde_entorno():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        return NotificadorTelegram(token, os.getenv("TELEGRAM_CHAT_ID_DEMO"))
    return NotificadorRegistro()
