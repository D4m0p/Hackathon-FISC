"""Roles y permisos de la API.

Cada petición protegida lleva `Authorization: Bearer <token>`. El token identifica un rol
(joven, empresa u orientador) y, para joven y empresa, a quién representa. En la base solo
se guarda el hash SHA-256 del token.
"""
from __future__ import annotations

import secrets
from typing import Callable, Literal

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from orquestador.almacen import Almacen

Rol = Literal["joven", "empresa", "orientador"]


class Identidad(BaseModel):
    rol: Rol
    sujeto: str | None = None   # joven_id o empresa_id; None para el orientador

    @property
    def es_orientador(self) -> bool:
        return self.rol == "orientador"

    def es_joven(self, joven_id: str) -> bool:
        return self.es_orientador or (self.rol == "joven" and self.sujeto == joven_id)

    def es_empresa(self, empresa_id: str) -> bool:
        return self.es_orientador or (self.rol == "empresa" and self.sujeto == empresa_id)


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def sin_permiso(detalle: str = "No tiene permiso para esta acción") -> HTTPException:
    return HTTPException(status_code=403, detail=detalle)


def dependencias(almacen: Almacen) -> tuple[Callable, Callable]:
    """Devuelve (identidad_opcional, identidad_requerida) para usar con Depends."""
    esquema = HTTPBearer(auto_error=False)

    def opcional(cred: HTTPAuthorizationCredentials | None = Depends(esquema)) -> Identidad | None:
        if cred is None:
            return None
        encontrada = almacen.credencial(cred.credentials)
        if encontrada is None:
            raise HTTPException(status_code=401, detail="Token inválido",
                                headers={"WWW-Authenticate": "Bearer"})
        return Identidad(rol=encontrada[0], sujeto=encontrada[1])

    def requerida(ident: Identidad | None = Depends(opcional)) -> Identidad:
        if ident is None:
            raise HTTPException(status_code=401, detail="Falta el token de acceso",
                                headers={"WWW-Authenticate": "Bearer"})
        return ident

    return opcional, requerida
