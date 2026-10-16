import os

# La app de api/main.py se construye al importarse: que use una base en memoria
# y nunca envíe mensajes reales durante las pruebas.
os.environ["RUTA_BASE_DATOS"] = ":memory:"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("CLAVE_ORIENTADOR", None)

TOKEN_ORIENTADOR = "t-orientador"


def cliente_orientador(orq):
    """TestClient de la API con el token del orientador ya puesto."""
    from fastapi.testclient import TestClient

    from api.main import crear_app
    orq.almacen.guardar_credencial(TOKEN_ORIENTADOR, "orientador", None)
    c = TestClient(crear_app(orq))
    c.headers["Authorization"] = f"Bearer {TOKEN_ORIENTADOR}"
    return c
