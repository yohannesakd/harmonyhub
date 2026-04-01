from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    SessionPrincipal,
    get_permissions_for_role,
    get_session_principal,
    get_user_memberships,
    memberships_to_context_choices,
    verify_csrf,
    verify_replay_headers,
)
from app.authz.abac import evaluate_abac
from app.authz.rbac import Permission
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_session_token
from app.db.models import Membership
from app.db.session import get_db_session
from app.schemas.context import ActiveContext, ContextChoice, ContextSetRequest, ContextSetResponse

router = APIRouter(prefix="/contexts", tags=["context"])


@router.get("/available", response_model=list[ContextChoice])
def available_contexts(
    principal: SessionPrincipal = Depends(get_session_principal),
    db: Session = Depends(get_db_session),
) -> list[ContextChoice]:
    memberships = get_user_memberships(principal, db)
    allowed = [membership for membership in memberships if Permission.CONTEXT_LIST in get_permissions_for_role(membership.role)]
    if not allowed:
        raise AppError(code="FORBIDDEN", message="Permission denied by RBAC", status_code=403)
    return memberships_to_context_choices(allowed, db)


@router.post("/active", response_model=ContextSetResponse, dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def set_active_context(
    payload: ContextSetRequest,
    response: Response,
    principal: SessionPrincipal = Depends(get_session_principal),
    db: Session = Depends(get_db_session),
) -> ContextSetResponse:
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == principal.user.id,
            Membership.organization_id == payload.organization_id,
            Membership.program_id == payload.program_id,
            Membership.event_id == payload.event_id,
            Membership.store_id == payload.store_id,
        )
    )
    if not membership:
        raise AppError(code="FORBIDDEN", message="Context not available for user", status_code=403)

    if Permission.CONTEXT_SWITCH not in get_permissions_for_role(membership.role):
        raise AppError(code="FORBIDDEN", message="Permission denied by RBAC", status_code=403)

    abac_decision = evaluate_abac(db, membership, surface="context", action="switch")
    if not abac_decision.allowed:
        raise AppError(
            code="FORBIDDEN",
            message="Permission denied by ABAC",
            status_code=403,
            details={"abac_reason": abac_decision.reason},
        )

    active_context = ActiveContext(
        organization_id=payload.organization_id,
        program_id=payload.program_id,
        event_id=payload.event_id,
        store_id=payload.store_id,
        role=membership.role,
    )

    settings = get_settings()
    token = create_session_token(
        subject=principal.user.id,
        username=principal.user.username,
        active_context=active_context.model_dump(),
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return ContextSetResponse(status="active_context_updated", active_context=active_context)
