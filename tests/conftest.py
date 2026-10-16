import os

# La app de api/main.py se construye al importarse: que use una base en memoria
# y nunca envíe mensajes reales durante las pruebas.
os.environ["RUTA_BASE_DATOS"] = ":memory:"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
