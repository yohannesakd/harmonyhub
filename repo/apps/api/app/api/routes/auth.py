from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pyotp
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
from app.authz.rbac import Permission
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_csrf_token, create_session_token, verify_password
from app.db.models import Membership, User
from app.db.session import get_db_session
from app.operations.audit import record_audit_event
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    TotpCodeRequest,
    TotpSetupResponse,
    TotpVerifyResponse,
    UserSummary,
)
from app.schemas.context import ActiveContext

router = APIRouter(prefix="/auth", tags=["auth"])


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _apply_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )


def _active_context_from_membership(membership: Membership | None) -> ActiveContext | None:
    if not membership:
        return None
    return ActiveContext(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        role=membership.role,
    )


def _active_role_for_principal(principal: SessionPrincipal, db: Session) -> str:
    if principal.active_context:
        return principal.active_context.role
    memberships = get_user_memberships(principal, db)
    if memberships:
        return memberships[0].role
    raise AppError(code="FORBIDDEN", message="No memberships available", status_code=403)


def _ensure_permission(principal: SessionPrincipal, db: Session, permission: Permission) -> None:
    role = _active_role_for_principal(principal, db)
    permission_set = get_permissions_for_role(role)
    if permission not in permission_set:
        raise AppError(code="FORBIDDEN", message="Permission denied by RBAC", status_code=403)


def _validate_totp(user: User, code: str | None) -> None:
    if not user.mfa_totp_enabled:
        return

    if not user.mfa_totp_secret:
        raise AppError(code="MFA_SETUP_INVALID", message="TOTP secret missing for MFA-enabled account", status_code=500)

    if not code:
        raise AppError(code="MFA_REQUIRED", message="MFA code is required", status_code=401)

    if not pyotp.TOTP(user.mfa_totp_secret).verify(code, valid_window=1):
        raise AppError(code="MFA_INVALID", message="Invalid MFA code", status_code=401)


def _user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        username=user.username,
        is_active=user.is_active,
        mfa_totp_enabled=user.mfa_totp_enabled,
    )


def _record_auth_audit(db: Session, user: User, *, action: str, details: dict | None = None) -> None:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at.asc()))
    if not membership:
        return
    record_audit_event(
        db,
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        actor_user_id=user.id,
        actor_role=membership.role,
        action=action,
        target_type="user",
        target_id=user.id,
        details=details,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db_session)) -> LoginResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user:
        raise AppError(code="AUTH_REQUIRED", message="Invalid credentials", status_code=401)

    if not user.is_active:
        if user.frozen_at:
            _record_auth_audit(
                db,
                user,
                action="auth.login.frozen_blocked",
                details={"reason": user.freeze_reason, "frozen_at": user.frozen_at.isoformat() if user.frozen_at else None},
            )
            db.commit()
            raise AppError(
                code="ACCOUNT_FROZEN",
                message="Account is frozen",
                status_code=423,
                details={"frozen_at": user.frozen_at.isoformat()},
            )
        raise AppError(code="AUTH_REQUIRED", message="Invalid credentials", status_code=401)

    now = datetime.now(UTC)
    locked_until = _as_utc(user.locked_until)
    if locked_until and locked_until > now:
        _record_auth_audit(
            db,
            user,
            action="auth.login.locked_blocked",
            details={"locked_until": locked_until.isoformat()},
        )
        db.commit()
        raise AppError(
            code="ACCOUNT_LOCKED",
            message="Account is temporarily locked",
            status_code=423,
            details={"locked_until": locked_until.isoformat()},
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
            user.failed_login_attempts = 0
        _record_auth_audit(
            db,
            user,
            action="auth.login.failed",
            details={"reason": "invalid_credentials", "failed_login_attempts": user.failed_login_attempts},
        )
        db.add(user)
        db.commit()
        raise AppError(code="AUTH_REQUIRED", message="Invalid credentials", status_code=401)

    try:
        _validate_totp(user, payload.totp_code)
    except AppError as exc:
        _record_auth_audit(db, user, action="auth.login.mfa_failed", details={"reason": exc.code})
        db.commit()
        raise

    user.failed_login_attempts = 0
    user.locked_until = None
    _record_auth_audit(db, user, action="auth.login.succeeded", details={"mfa_enabled": user.mfa_totp_enabled})
    db.add(user)
    db.commit()

    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at.asc())).all()
    active_membership = memberships[0] if memberships else None
    active_context = _active_context_from_membership(active_membership)
    permissions = sorted(get_permissions_for_role(active_membership.role if active_membership else ""))

    session_token = create_session_token(
        subject=user.id,
        username=user.username,
        active_context=active_context.model_dump() if active_context else {},
    )
    csrf_token = create_csrf_token()
    _apply_session_cookies(response, session_token, csrf_token)

    return LoginResponse(
        user=_user_summary(user),
        csrf_token=csrf_token,
        active_context=active_context,
        permissions=[permission.value for permission in permissions],
    )


@router.post("/logout", dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def logout(response: Response) -> dict:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name)
    response.delete_cookie(settings.csrf_cookie_name)
    return {"status": "logged_out"}


@router.get("/me", response_model=MeResponse)
def me(
    principal: SessionPrincipal = Depends(get_session_principal),
    db: Session = Depends(get_db_session),
) -> MeResponse:
    memberships = get_user_memberships(principal, db)
    contexts = memberships_to_context_choices(memberships, db)

    active_context = principal.active_context
    if not active_context and memberships:
        active_context = _active_context_from_membership(memberships[0])

    active_permissions: list[str] = []
    if active_context:
        active_permission_set = get_permissions_for_role(active_context.role)
        if Permission.AUTH_ME_READ not in active_permission_set:
            raise AppError(code="FORBIDDEN", message="Permission denied by RBAC", status_code=403)
        active_permissions = sorted(permission.value for permission in active_permission_set)

    return MeResponse(
        user=_user_summary(principal.user),
        active_context=active_context,
        permissions=active_permissions,
        available_contexts=contexts,
    )


@router.post(
    "/mfa/totp/setup",
    response_model=TotpSetupResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def setup_totp(
    principal: SessionPrincipal = Depends(get_session_principal),
    db: Session = Depends(get_db_session),
) -> TotpSetupResponse:
    _ensure_permission(principal, db, Permission.AUTH_MFA_MANAGE)
    secret = pyotp.random_base32()
    principal.user.mfa_totp_secret = secret
    principal.user.mfa_totp_enabled = False
    db.add(principal.user)
    db.commit()

    totp = pyotp.TOTP(secret)
    return TotpSetupResponse(
        secret=secret,
        otpauth_uri=totp.provisioning_uri(name=principal.user.username, issuer_name="HarmonyHub"),
    )


@router.post(
    "/mfa/totp/verify",
    response_model=TotpVerifyResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def verify_totp(
    payload: TotpCodeRequest,
    principal: SessionPrincipal = Depends(get_session_principal),
    db: Session = Depends(get_db_session),
) -> TotpVerifyResponse:
    _ensure_permission(principal, db, Permission.AUTH_MFA_MANAGE)
    if not principal.user.mfa_totp_secret:
        raise AppError(code="MFA_SETUP_REQUIRED", message="No TOTP secret configured", status_code=400)

    valid = pyotp.TOTP(principal.user.mfa_totp_secret).verify(payload.code, valid_window=1)
    return TotpVerifyResponse(valid=valid, mfa_totp_enabled=principal.user.mfa_totp_enabled)


@router.post(
    "/mfa/totp/enable",
    response_model=TotpVerifyResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def enable_totp(
    payload: TotpCodeRequest,
    principal: SessionPrincipal = Depends(get_session_principal),
    db: Session = Depends(get_db_session),
) -> TotpVerifyResponse:
    _ensure_permission(principal, db, Permission.AUTH_MFA_MANAGE)
    if not principal.user.mfa_totp_secret:
        raise AppError(code="MFA_SETUP_REQUIRED", message="No TOTP secret configured", status_code=400)

    valid = pyotp.TOTP(principal.user.mfa_totp_secret).verify(payload.code, valid_window=1)
    if not valid:
        raise AppError(code="MFA_INVALID", message="Invalid MFA code", status_code=401)

    principal.user.mfa_totp_enabled = True
    db.add(principal.user)
    db.commit()
    return TotpVerifyResponse(valid=True, mfa_totp_enabled=True)
