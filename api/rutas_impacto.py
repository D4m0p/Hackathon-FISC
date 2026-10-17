"""Rutas de la cifra de impacto: cuántos pares descarta el sistema y por qué."""
from fastapi import APIRouter, Depends

from orquestador.impacto import Impacto, ImpactoJoven, impacto, impacto_joven

from .seguridad import Identidad, sin_permiso


def crear_router(orq, solo_orientador, requerida) -> APIRouter:
    router = APIRouter()

    @router.get("/impacto")
    def cifra_de_impacto(_: Identidad = Depends(solo_orientador)) -> Impacto:
        return impacto(orq)

    @router.get("/jovenes/{joven_id}/impacto")
    def impacto_del_joven(joven_id: str, ident: Identidad = Depends(requerida)) -> ImpactoJoven:
        if not ident.es_joven(joven_id):
            raise sin_permiso()
        return impacto_joven(orq, joven_id)

    return router
