"""Persistencia en SQLite. Cada entidad se guarda como JSON validado por el contrato."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from datetime import datetime, timezone
from typing import TypeVar

from pydantic import BaseModel

from contrato.modelos import (
    Asignacion, Curso, DatosPersonales, Habilidad, Joven, PlanFormacion, Traslado, Traza, Vacante,
)

M = TypeVar("M", bound=BaseModel)

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS entidades (
    tipo TEXT NOT NULL, id TEXT NOT NULL, datos TEXT NOT NULL,
    PRIMARY KEY (tipo, id)
);
CREATE TABLE IF NOT EXISTS deslizamientos (
    actor TEXT NOT NULL CHECK (actor IN ('joven', 'empresa')),
    joven_id TEXT NOT NULL, vacante_id TEXT NOT NULL, le_interesa INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    PRIMARY KEY (actor, joven_id, vacante_id)
);
CREATE TABLE IF NOT EXISTS trazas (
    n INTEGER PRIMARY KEY AUTOINCREMENT, agente TEXT NOT NULL, datos TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS credenciales (
    token_hash TEXT PRIMARY KEY,
    rol TEXT NOT NULL CHECK (rol IN ('joven', 'empresa', 'orientador')),
    sujeto TEXT
);
CREATE TABLE IF NOT EXISTS mensajes (
    n INTEGER PRIMARY KEY AUTOINCREMENT, destino TEXT, texto TEXT NOT NULL,
    enviado INTEGER NOT NULL, fecha TEXT NOT NULL
);
"""

_TIPOS: dict[type[BaseModel], str] = {
    Joven: "joven", DatosPersonales: "datos_personales", Vacante: "vacante", Curso: "curso",
    Asignacion: "asignacion", PlanFormacion: "plan", Habilidad: "habilidad",
}


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def clave_asignacion(a: Asignacion) -> str:
    return f"{a.joven_id}|{a.vacante_id}"


def _id(obj: BaseModel) -> str:
    if isinstance(obj, DatosPersonales | PlanFormacion):
        return obj.joven_id
    if isinstance(obj, Asignacion):
        return clave_asignacion(obj)
    if isinstance(obj, Habilidad):
        return obj.codigo
    return obj.id


class Almacen:
    def __init__(self, ruta: str = ":memory:"):
        self._con = sqlite3.connect(ruta, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._con.executescript(_ESQUEMA)

    # ---------- entidades ----------
    def guardar(self, obj: BaseModel) -> None:
        with self._lock, self._con:
            self._con.execute(
                "INSERT INTO entidades (tipo, id, datos) VALUES (?, ?, ?) "
                "ON CONFLICT (tipo, id) DO UPDATE SET datos = excluded.datos",
                (_TIPOS[type(obj)], _id(obj), obj.model_dump_json()))

    def obtener(self, modelo: type[M], id: str) -> M | None:
        with self._lock:
            fila = self._con.execute("SELECT datos FROM entidades WHERE tipo = ? AND id = ?",
                                     (_TIPOS[modelo], id)).fetchone()
        return modelo.model_validate_json(fila[0]) if fila else None

    def listar(self, modelo: type[M]) -> list[M]:
        with self._lock:
            filas = self._con.execute("SELECT datos FROM entidades WHERE tipo = ? ORDER BY id",
                                      (_TIPOS[modelo],)).fetchall()
        return [modelo.model_validate_json(f[0]) for f in filas]

    def borrar(self, modelo: type[BaseModel], id: str) -> None:
        with self._lock, self._con:
            self._con.execute("DELETE FROM entidades WHERE tipo = ? AND id = ?", (_TIPOS[modelo], id))

    def borrar_tipo(self, modelo: type[BaseModel]) -> None:
        with self._lock, self._con:
            self._con.execute("DELETE FROM entidades WHERE tipo = ?", (_TIPOS[modelo],))

    # ---------- traslados (tabla de referencia) ----------
    def guardar_traslados(self, traslados: list[Traslado]) -> None:
        with self._lock, self._con:
            self._con.execute("DELETE FROM entidades WHERE tipo = 'traslado'")
            self._con.executemany(
                "INSERT INTO entidades (tipo, id, datos) VALUES ('traslado', ?, ?)",
                [(f"{t.origen}|{t.destino}", t.model_dump_json()) for t in traslados])

    def traslados(self) -> list[Traslado]:
        with self._lock:
            filas = self._con.execute(
                "SELECT datos FROM entidades WHERE tipo = 'traslado' ORDER BY id").fetchall()
        return [Traslado.model_validate_json(f[0]) for f in filas]

    # ---------- deslizamientos ----------
    def deslizar(self, actor: str, joven_id: str, vacante_id: str, le_interesa: bool) -> None:
        with self._lock, self._con:
            self._con.execute(
                "INSERT INTO deslizamientos VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (actor, joven_id, vacante_id) DO UPDATE SET "
                "le_interesa = excluded.le_interesa, fecha = excluded.fecha",
                (actor, joven_id, vacante_id, int(le_interesa), _ahora()))

    def interes_mutuo(self) -> set[tuple[str, str]]:
        with self._lock:
            filas = self._con.execute(
                "SELECT j.joven_id, j.vacante_id FROM deslizamientos j "
                "JOIN deslizamientos e ON e.joven_id = j.joven_id AND e.vacante_id = j.vacante_id "
                "WHERE j.actor = 'joven' AND e.actor = 'empresa' "
                "AND j.le_interesa = 1 AND e.le_interesa = 1").fetchall()
        return {(a, b) for a, b in filas}

    def ya_deslizo(self, actor: str, joven_id: str, vacante_id: str) -> bool:
        with self._lock:
            return self._con.execute(
                "SELECT 1 FROM deslizamientos WHERE actor = ? AND joven_id = ? AND vacante_id = ?",
                (actor, joven_id, vacante_id)).fetchone() is not None

    # ---------- trazas ----------
    def registrar_traza(self, traza: Traza) -> None:
        with self._lock, self._con:
            self._con.execute("INSERT INTO trazas (agente, datos) VALUES (?, ?)",
                              (traza.agente.value, traza.model_dump_json()))

    def trazas(self, agente: str | None = None, limite: int = 500) -> list[Traza]:
        consulta = "SELECT datos FROM trazas"
        params: tuple = ()
        if agente:
            consulta += " WHERE agente = ?"
            params = (agente,)
        consulta += " ORDER BY n DESC LIMIT ?"
        with self._lock:
            filas = self._con.execute(consulta, params + (limite,)).fetchall()
        return [Traza.model_validate_json(f[0]) for f in filas]

    # ---------- credenciales (solo se guarda el hash del token) ----------
    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def guardar_credencial(self, token: str, rol: str, sujeto: str | None) -> None:
        with self._lock, self._con:
            self._con.execute(
                "INSERT INTO credenciales VALUES (?, ?, ?) ON CONFLICT (token_hash) DO UPDATE SET "
                "rol = excluded.rol, sujeto = excluded.sujeto", (self._hash(token), rol, sujeto))

    def credencial(self, token: str) -> tuple[str, str | None] | None:
        with self._lock:
            fila = self._con.execute("SELECT rol, sujeto FROM credenciales WHERE token_hash = ?",
                                     (self._hash(token),)).fetchone()
        return (fila[0], fila[1]) if fila else None

    # ---------- mensajes enviados ----------
    def registrar_mensaje(self, destino: str | None, texto: str, enviado: bool) -> None:
        with self._lock, self._con:
            self._con.execute("INSERT INTO mensajes (destino, texto, enviado, fecha) VALUES (?, ?, ?, ?)",
                              (destino, texto, int(enviado), _ahora()))

    def mensajes(self) -> list[dict]:
        with self._lock:
            filas = self._con.execute(
                "SELECT destino, texto, enviado, fecha FROM mensajes ORDER BY n").fetchall()
        return [dict(destino=d, texto=t, enviado=bool(e), fecha=f) for d, t, e, f in filas]


__all__ = ["Almacen", "clave_asignacion"]
