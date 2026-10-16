"""Envío de mensajes. Telegram si hay token; si no, solo queda registrado."""
from __future__ import annotations

import os

import httpx


class NotificadorRegistro:
    """No envía nada; el orquestador igual guarda el mensaje en la base."""

    def enviar(self, destino: str | None, texto: str) -> bool:
        return False


class NotificadorTelegram:
    def __init__(self, token: str, chat_por_defecto: str | None = None, timeout: float = 10):
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_por_defecto = chat_por_defecto
        self._timeout = timeout

    def enviar(self, destino: str | None, texto: str) -> bool:
        chat = destino or self._chat_por_defecto
        if not chat:
            return False
        try:
            r = httpx.post(self._url, json={"chat_id": chat, "text": texto}, timeout=self._timeout)
            return r.status_code == 200 and r.json().get("ok", False)
        except httpx.HTTPError:
            return False


def desde_entorno():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        return NotificadorTelegram(token, os.getenv("TELEGRAM_CHAT_ID_DEMO"))
    return NotificadorRegistro()
