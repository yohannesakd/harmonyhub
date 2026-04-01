from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.authz.abac import AbacDecision, build_subject_attributes, evaluate_abac
from app.authz.rbac import Permission, has_permission
from app.core.errors import AppError
from app.core.security import decode_session_token
from app.db.models import Event, Membership, Organization, Program, ReplayNonce, Store, User
from app.db.session import get_db_session
from app.schemas.context import ActiveContext, ContextChoice


@dataclass
class SessionPrincipal:
    user: User
    session_payload: dict[str, Any]
    active_context: ActiveContext | None


@dataclass
class AuthorizedMembership:
    principal: SessionPrincipal
    membership: Membership
    permissions: set[Permission]
    abac_decision: AbacDecision


def _parse_timestamp(raw: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppError(code="REPLAY_REJECTED", message="Invalid request timestamp", status_code=409) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _extract_active_context(payload: dict[str, Any]) -> ActiveContext | None:
    ctx = payload.get("ctx") or {}
    required_fields = {"organization_id", "program_id", "event_id", "store_id", "role"}
    if not required_fields.issubset(set(ctx.keys())):
        return None
    try:
        return ActiveContext(**ctx)
    except Exception:  # noqa: BLE001
        return None


def verify_replay_headers(
    x_request_nonce: str | None = Header(default=None),
    x_request_timestamp: str | None = Header(default=None),
    request: Request = None,
    db: Session = Depends(get_db_session),
) -> None:
    if request and request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    if not x_request_nonce or not x_request_timestamp:
        raise AppError(code="REPLAY_REJECTED", message="Missing replay headers", status_code=409)

    request_time = _parse_timestamp(x_request_timestamp)
    now = datetime.now(UTC)
    if abs(now - request_time) > timedelta(minutes=5):
        raise AppError(code="REPLAY_REJECTED", message="Request timestamp outside replay window", status_code=409)

    valid_since = now - timedelta(minutes=5)
    db.execute(delete(ReplayNonce).where(ReplayNonce.created_at < valid_since))

    user_id: str | None = None
    if request:
        token = request.cookies.get("hh_session")
        if token:
            try:
                user_id = decode_session_token(token).get("sub")
            except Exception:  # noqa: BLE001
                user_id = None

    nonce_record = ReplayNonce(
        nonce=x_request_nonce,
        request_method=request.method if request else "UNKNOWN",
        request_path=request.url.path if request else "UNKNOWN",
        user_id=user_id,
        created_at=now,
    )

    db.add(nonce_record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(code="REPLAY_REJECTED", message="Nonce has already been used", status_code=409) from exc


def verify_csrf(
    request: Request,
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    csrf_cookie: str | None = Cookie(default=None, alias="hh_csrf"),
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        raise AppError(code="CSRF_INVALID", message="CSRF token mismatch", status_code=403)


def get_session_principal(
    session_cookie: str | None = Cookie(default=None, alias="hh_session"),
    db: Session = Depends(get_db_session),
) -> SessionPrincipal:
    if not session_cookie:
        raise AppError(code="AUTH_REQUIRED", message="Authentication required", status_code=401)

    try:
        payload = decode_session_token(session_cookie)
    except Exception as exc:  # noqa: BLE001
        raise AppError(code="AUTH_REQUIRED", message="Invalid session", status_code=401) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise AppError(code="AUTH_REQUIRED", message="Invalid session payload", status_code=401)

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppError(code="AUTH_REQUIRED", message="User inactive", status_code=401)

    if not user.is_active:
        if user.frozen_at:
            raise AppError(
                code="ACCOUNT_FROZEN",
                message="Account is frozen",
                status_code=423,
                details={"frozen_at": user.frozen_at.isoformat()},
            )
        raise AppError(code="AUTH_REQUIRED", message="User inactive", status_code=401)

    return SessionPrincipal(user=user, session_payload=payload, active_context=_extract_active_context(payload))


def _resolve_membership_from_active_context(principal: SessionPrincipal, db: Session) -> Membership | None:
    if not principal.active_context:
        return None
    ctx = principal.active_context
    return db.scalar(
        select(Membership).where(
            Membership.user_id == principal.user.id,
            Membership.organization_id == ctx.organization_id,
            Membership.program_id == ctx.program_id,
            Membership.event_id == ctx.event_id,
            Membership.store_id == ctx.store_id,
            Membership.role == ctx.role,
        )
    )


def get_user_memberships(principal: SessionPrincipal, db: Session) -> list[Membership]:
    return db.scalars(
        select(Membership)
        .where(Membership.user_id == principal.user.id)
        .order_by(
            Membership.organization_id.asc(),
            Membership.program_id.asc(),
            Membership.event_id.asc(),
            Membership.store_id.asc(),
        )
    ).all()


def get_active_membership(principal: SessionPrincipal, db: Session) -> Membership:
    membership = _resolve_membership_from_active_context(principal, db)
    if membership:
        return membership

    memberships = get_user_memberships(principal, db)
    if not memberships:
        raise AppError(code="FORBIDDEN", message="No memberships available", status_code=403)

    return memberships[0]


def memberships_to_context_choices(memberships: list[Membership], db: Session) -> list[ContextChoice]:
    choices: list[ContextChoice] = []
    for membership in memberships:
        org = db.scalar(select(Organization).where(Organization.id == membership.organization_id))
        program = db.scalar(select(Program).where(Program.id == membership.program_id))
        event = db.scalar(select(Event).where(Event.id == membership.event_id))
        store = db.scalar(select(Store).where(Store.id == membership.store_id))
        if not org or not program or not event or not store:
            continue
        choices.append(
            ContextChoice(
                organization_id=membership.organization_id,
                organization_name=org.name,
                program_id=membership.program_id,
                program_name=program.name,
                event_id=membership.event_id,
                event_name=event.name,
                store_id=membership.store_id,
                store_name=store.name,
                role=membership.role,
            )
        )
    return choices


def get_permissions_for_role(role: str) -> set[Permission]:
    return {permission for permission in Permission if has_permission(role, permission)}


def authorize_for_active_context(
    permission: Permission,
    *,
    surface: str,
    action: str,
):
    def dependency(
        principal: SessionPrincipal = Depends(get_session_principal),
        db: Session = Depends(get_db_session),
    ) -> AuthorizedMembership:
        membership = get_active_membership(principal, db)
        permissions = get_permissions_for_role(membership.role)
        if permission not in permissions:
            raise AppError(code="FORBIDDEN", message="Permission denied by RBAC", status_code=403)

        abac_decision = evaluate_abac(
            db,
            membership,
            surface=surface,
            action=action,
            subject=build_subject_attributes(principal.user),
        )
        if not abac_decision.allowed:
            raise AppError(
                code="FORBIDDEN",
                message="Permission denied by ABAC",
                status_code=403,
                details={"abac_reason": abac_decision.reason, "matched_rule_id": abac_decision.matched_rule_id},
            )

        return AuthorizedMembership(
            principal=principal,
            membership=membership,
            permissions=permissions,
            abac_decision=abac_decision,
        )

    return dependency
