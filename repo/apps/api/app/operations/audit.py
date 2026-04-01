from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Membership

_REDACT_KEYS = {
    "password",
    "totp_code",
    "token",
    "secret",
    "csrf",
    "nonce",
    "pickup_code",
    "code",
    "raw_bytes",
    "file_bytes",
    "email",
    "phone",
    "address",
    "address_line1",
    "line1",
    "line2",
    "postal_code",
    "recipient_name",
}

_REDACT_KEY_SUBSTRINGS = {
    "email",
    "phone",
    "address",
    "postal",
    "recipient",
}


def _should_redact_key(key: str) -> bool:
    key_lower = key.lower()
    if key_lower in _REDACT_KEYS:
        return True
    if any(fragment in key_lower for fragment in _REDACT_KEY_SUBSTRINGS):
        return True
    return False


def sanitize_audit_details(value):
    if isinstance(value, dict):
        redacted: dict = {}
        for key, child in value.items():
            if _should_redact_key(key):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = sanitize_audit_details(child)
        return redacted
    if isinstance(value, list):
        return [sanitize_audit_details(item) for item in value]
    return value


def record_audit_event(
    db: Session,
    *,
    organization_id: str,
    program_id: str | None,
    event_id: str | None,
    store_id: str | None,
    actor_user_id: str | None,
    actor_role: str | None,
    action: str,
    target_type: str | None,
    target_id: str | None,
    details: dict | None,
) -> None:
    db.add(
        AuditEvent(
            organization_id=organization_id,
            program_id=program_id,
            event_id=event_id,
            store_id=store_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details_json=sanitize_audit_details(details or {}),
        )
    )


def record_membership_audit_event(
    db: Session,
    membership: Membership,
    *,
    action: str,
    target_type: str | None,
    target_id: str | None,
    details: dict | None,
) -> None:
    record_audit_event(
        db,
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        actor_user_id=membership.user_id,
        actor_role=membership.role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


def list_audit_events_for_scope(
    db: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    action_prefix: str | None,
    actor_user_id: str | None,
    target_type: str | None,
    target_id: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
    limit: int,
) -> list[AuditEvent]:
    query: Select[tuple[AuditEvent]] = (
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == organization_id,
            AuditEvent.program_id == program_id,
            AuditEvent.event_id == event_id,
            AuditEvent.store_id == store_id,
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )

    if action_prefix:
        query = query.where(AuditEvent.action.like(f"{action_prefix}%"))
    if actor_user_id:
        query = query.where(AuditEvent.actor_user_id == actor_user_id)
    if target_type:
        query = query.where(AuditEvent.target_type == target_type)
    if target_id:
        query = query.where(AuditEvent.target_id == target_id)
    if start_at:
        query = query.where(AuditEvent.created_at >= start_at)
    if end_at:
        query = query.where(AuditEvent.created_at <= end_at)

    return db.scalars(query).all()
