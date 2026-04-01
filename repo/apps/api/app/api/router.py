from fastapi import APIRouter

from app.api.routes import (
    auth,
    context,
    dashboard,
    directory,
    fulfillment,
    health,
    imports_admin,
    operations,
    ordering,
    policies,
    recommendations,
    repertoire,
)


def build_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    router.include_router(auth.router)
    router.include_router(context.router)
    router.include_router(dashboard.router)
    router.include_router(directory.router)
    router.include_router(repertoire.router)
    router.include_router(ordering.menu_router)
    router.include_router(ordering.address_router)
    router.include_router(ordering.scheduling_router)
    router.include_router(ordering.orders_router)
    router.include_router(fulfillment.router)
    router.include_router(imports_admin.uploads_router)
    router.include_router(imports_admin.imports_router)
    router.include_router(imports_admin.accounts_router)
    router.include_router(operations.router)
    router.include_router(recommendations.recommendations_router)
    router.include_router(recommendations.pairing_router)
    router.include_router(policies.router)
    return router
