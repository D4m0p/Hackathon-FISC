from fastapi.testclient import TestClient

from api.main import crear_app
from orquestador import Almacen, Orquestador


def test_transcribir_tambien_tiene_limite_para_anonimos():
    c = TestClient(crear_app(Orquestador(Almacen()), limite_anonimo_por_minuto=2))
    estados = [c.post("/perfil/transcribir", json={}).status_code for _ in range(3)]
    assert estados[-1] == 429 and 429 not in estados[:2]
