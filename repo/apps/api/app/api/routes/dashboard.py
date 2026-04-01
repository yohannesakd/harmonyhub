from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthorizedMembership, authorize_for_active_context
from app.authz.rbac import Permission
from app.core.errors import AppError
from app.db.models import Event, Organization, Program, Store
from app.db.session import get_db_session
from app.schemas.context import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/event",
    response_model=DashboardResponse,
)
def event_dashboard(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.DASHBOARD_VIEW, surface="dashboard", action="view")
    ),
    db: Session = Depends(get_db_session),
) -> DashboardResponse:
    membership = authorized.membership

    event = db.scalar(select(Event).where(Event.id == membership.event_id))
    store = db.scalar(select(Store).where(Store.id == membership.store_id))
    program = db.scalar(select(Program).where(Program.id == membership.program_id))
    org = db.scalar(select(Organization).where(Organization.id == membership.organization_id))

    if not event or not store or not org or not program:
        raise AppError(code="VALIDATION_ERROR", message="Context references are invalid", status_code=422)

    return DashboardResponse(
        event_name=event.name,
        store_name=store.name,
        organization_name=org.name,
        user_role=membership.role,
        permissions=sorted(permission.value for permission in authorized.permissions),
        abac_enforced=authorized.abac_decision.enforced,
        notes=[
            "Dashboard reflects active session context and role-scoped permissions.",
            "RBAC default-deny is enforced via reusable authorization guards.",
            "ABAC hooks are active where surfaces are enabled by tenant policy.",
        ],
    )
