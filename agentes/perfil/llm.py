"""Cliente del LLM. El agente solo depende del protocolo `ClienteLLM`, así las pruebas
usan un cliente falso y la demo puede correr sin clave (cae a palabras clave)."""
from __future__ import annotations

import base64
import json
import os
from typing import Protocol

MODELO_TEXTO = "openai/gpt-oss-120b"
MODELO_VISION = "qwen/qwen3.8-27b"


class ErrorLLM(Exception):
    """El LLM no respondió o respondió algo que no es JSON."""


class ClienteLLM(Protocol):
    def json(self, sistema: str, usuario: str) -> dict:
        """Devuelve un objeto JSON (sin validar: lo valida quien llama)."""

    def json_con_imagen(self, sistema: str, instruccion: str, imagen: bytes, tipo_mime: str) -> dict:
        """Igual, con una imagen adjunta."""


class ClienteGroq:
    def __init__(self, clave: str | None = None, modelo: str | None = None,
                 modelo_vision: str | None = None):
        from groq import Groq   # import tardío: las pruebas no lo necesitan

        clave = clave or os.getenv("GROQ_API_KEY")
        if not clave:
            raise ErrorLLM("Falta GROQ_API_KEY")
        self._cliente = Groq(api_key=clave, timeout=30)
        self.modelo = modelo or os.getenv("GROQ_MODELO") or MODELO_TEXTO
        self.modelo_vision = modelo_vision or os.getenv("GROQ_MODELO_VISION") or MODELO_VISION

    def _pedir(self, modelo: str, mensajes: list[dict]) -> dict:
        try:
            r = self._cliente.chat.completions.create(
                model=modelo, messages=mensajes, temperature=0,
                response_format={"type": "json_object"}, max_completion_tokens=2000)
            datos = json.loads(r.choices[0].message.content or "")
        except Exception as e:  # red, cuota, JSON roto: todo se trata igual
            raise ErrorLLM(str(e)) from e
        if not isinstance(datos, dict):
            raise ErrorLLM("La respuesta no es un objeto JSON")
        return datos

    def json(self, sistema: str, usuario: str) -> dict:
        return self._pedir(self.modelo, [{"role": "system", "content": sistema},
                                         {"role": "user", "content": usuario}])

    def json_con_imagen(self, sistema: str, instruccion: str, imagen: bytes, tipo_mime: str) -> dict:
        url = f"data:{tipo_mime};base64,{base64.b64encode(imagen).decode()}"
        return self._pedir(self.modelo_vision, [
            {"role": "system", "content": sistema},
            {"role": "user", "content": [{"type": "text", "text": instruccion},
                                         {"type": "image_url", "image_url": {"url": url}}]}])


def cliente_desde_entorno() -> ClienteLLM | None:
    """None si no hay clave: el agente sigue funcionando con palabras clave."""
    try:
        return ClienteGroq()
    except ErrorLLM:
        return None
