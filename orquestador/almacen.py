"""Persistencia en SQLite. Cada entidad se guarda como JSON validado por el contrato."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from datetime import datetime, timezone
from typing import TypeVar

from pydantic import BaseModel

from contrato.modelos import (
    Asignacion, Curso, DatosPersonales, Habilidad, Joven, Pesos, PlanFormacion, Traslado, Traza, Vacante,
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
    Asignacion: "asignacion", PlanFormacion: "plan", Habilidad: "habilidad", Pesos: "config",
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
    if isinstance(obj, Pesos):
        return "pesos"
    return obj.id


class Almacen:
    def __init__(self, ruta: str = ":memory:"):
        self._con = sqlite3.connect(ruta, check_same_thread=False)
        self._lock = threading.Lock()
        self._traslados: list[Traslado] | None = None   # caché; se invalida al guardar
        with self._lock:
            if ruta != ":memory:":
                # WAL: escrituras más rápidas y lecturas que no esperan a las escrituras
                self._con.execute("PRAGMA journal_mode=WAL")
                self._con.execute("PRAGMA synchronous=NORMAL")
            self._con.executescript(_ESQUEMA)

    def responde(self) -> bool:
        """La base contesta una consulta mínima (para /salud)."""
        try:
            with self._lock:
                return self._con.execute("SELECT 1").fetchone() == (1,)
        except sqlite3.Error:
            return False

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
        self._traslados = None
        with self._lock, self._con:
            self._con.execute("DELETE FROM entidades WHERE tipo = 'traslado'")
            self._con.executemany(
                "INSERT INTO entidades (tipo, id, datos) VALUES ('traslado', ?, ?)",
                [(f"{t.origen}|{t.destino}", t.model_dump_json()) for t in traslados])

    def traslados(self) -> list[Traslado]:
        if self._traslados is None:
            with self._lock:
                filas = self._con.execute(
                    "SELECT datos FROM entidades WHERE tipo = 'traslado' ORDER BY id").fetchall()
            self._traslados = [Traslado.model_validate_json(f[0]) for f in filas]
        return list(self._traslados)

    # ---------- asignaciones filtradas (id = "joven|vacante"; los ids no llevan "|") ----------
    def asignaciones(self, joven_id: str | None = None, vacante_id: str | None = None) -> list[Asignacion]:
        consulta = "SELECT datos FROM entidades WHERE tipo = 'asignacion'"
        params: list[str] = []
        if joven_id is not None:
            consulta += " AND substr(id, 1, length(?) + 1) = ? || '|'"
            params += [joven_id, joven_id]
        if vacante_id is not None:
            consulta += " AND substr(id, -length(?) - 1) = '|' || ?"
            params += [vacante_id, vacante_id]
        with self._lock:
            filas = self._con.execute(consulta + " ORDER BY id", params).fetchall()
        return [Asignacion.model_validate_json(f[0]) for f in filas]

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

    def decidir_si_pendiente(self, a: Asignacion) -> bool:
        """Guarda la decisión SOLO si la asignación sigue pendiente y vigente en la base
        (compara y cambia en una sola sentencia). False = otro proceso ya decidió."""
        with self._lock, self._con:
            cur = self._con.execute(
                "UPDATE entidades SET datos = ? WHERE tipo = 'asignacion' AND id = ? "
                "AND json_extract(datos, '$.aprobada') IS NULL AND json_extract(datos, '$.vigente') = 1",
                (a.model_dump_json(), clave_asignacion(a)))
            return cur.rowcount == 1

    def hay_interes_mutuo(self, joven_id: str, vacante_id: str) -> bool:
        with self._lock:
            n = self._con.execute(
                "SELECT COUNT(*) FROM deslizamientos WHERE joven_id = ? AND vacante_id = ? "
                "AND le_interesa = 1 AND actor IN ('joven', 'empresa')", (joven_id, vacante_id)).fetchone()[0]
        return n == 2

    def deslizadas_por_joven(self, joven_id: str) -> set[str]:
        """Vacantes que el joven ya deslizó (en una sola consulta)."""
        with self._lock:
            filas = self._con.execute("SELECT vacante_id FROM deslizamientos WHERE actor = 'joven' "
                                      "AND joven_id = ?", (joven_id,)).fetchall()
        return {f[0] for f in filas}

    def deslizados_por_empresa(self, vacante_id: str) -> set[str]:
        """Jóvenes que la empresa ya deslizó en esa vacante (en una sola consulta)."""
        with self._lock:
            filas = self._con.execute("SELECT joven_id FROM deslizamientos WHERE actor = 'empresa' "
                                      "AND vacante_id = ?", (vacante_id,)).fetchall()
        return {f[0] for f in filas}

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

    def trazas_de_joven(self, joven_id: str) -> list[Traza]:
        """Trazas que mencionan al joven, en orden cronológico: las que lo tienen como
        entrada y los reacomodos que lo propusieron (salida.nuevas = "joven|vacante")."""
        with self._lock:
            filas = self._con.execute(
                "SELECT datos FROM trazas WHERE json_extract(datos, '$.entrada.joven_id') = ? "
                "OR EXISTS (SELECT 1 FROM json_each(datos, '$.salida.nuevas') "
                "           WHERE substr(value, 1, length(?) + 1) = ? || '|') "
                "ORDER BY n", (joven_id, joven_id, joven_id)).fetchall()
        return [Traza.model_validate_json(f[0]) for f in filas]

    def deslizamientos_de(self, joven_id: str) -> list[dict]:
        with self._lock:
            filas = self._con.execute(
                "SELECT actor, vacante_id, le_interesa, fecha FROM deslizamientos "
                "WHERE joven_id = ? ORDER BY fecha, actor, vacante_id", (joven_id,)).fetchall()
        return [dict(actor=a, vacante_id=v, le_interesa=bool(i), fecha=f) for a, v, i, f in filas]

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
