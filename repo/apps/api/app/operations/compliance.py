from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Membership, RecoveryDrillRun


@dataclass(frozen=True)
class RecoveryDrillCompliance:
    status: str
    latest_performed_at: datetime | None
    due_at: datetime | None
    days_until_due: int | None
    days_overdue: int


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def retention_cutoff(*, retention_days: int, now: datetime | None = None) -> datetime:
    reference = now or utc_now()
    return reference - timedelta(days=retention_days)


def prune_audit_events_for_retention(db: Session, *, retention_days: int, now: datetime | None = None) -> int:
    cutoff = retention_cutoff(retention_days=retention_days, now=now)
    result = db.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff))
    return int(result.rowcount or 0)


def count_scope_audit_events_older_than(
    db: Session,
    *,
    organization_id: str,
    program_id: str,
    event_id: str,
    store_id: str,
    cutoff_at: datetime,
) -> int:
    count = db.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.organization_id == organization_id,
            AuditEvent.program_id == program_id,
            AuditEvent.event_id == event_id,
            AuditEvent.store_id == store_id,
            AuditEvent.created_at < cutoff_at,
        )
    )
    return int(count or 0)


def evaluate_recovery_drill_compliance(
    *,
    latest_performed_at: datetime | None,
    interval_days: int,
    now: datetime | None = None,
) -> RecoveryDrillCompliance:
    reference = as_utc(now) if now is not None else utc_now()
    if latest_performed_at is None:
        return RecoveryDrillCompliance(
            status="overdue",
            latest_performed_at=None,
            due_at=None,
            days_until_due=None,
            days_overdue=interval_days,
        )

    due_at = as_utc(latest_performed_at) + timedelta(days=interval_days)
    delta_days = (due_at - reference).days
    if reference <= due_at:
        return RecoveryDrillCompliance(
            status="current",
            latest_performed_at=latest_performed_at,
            due_at=due_at,
            days_until_due=max(delta_days, 0),
            days_overdue=0,
        )

    return RecoveryDrillCompliance(
        status="overdue",
        latest_performed_at=latest_performed_at,
        due_at=due_at,
        days_until_due=0,
        days_overdue=max((reference - due_at).days, 1),
    )


def count_overdue_recovery_drill_scopes(db: Session, *, interval_days: int, now: datetime | None = None) -> int:
    reference = now or utc_now()
    cutoff = reference - timedelta(days=interval_days)

    scopes = (
        select(
            Membership.organization_id,
            Membership.program_id,
            Membership.event_id,
            Membership.store_id,
        )
        .distinct()
        .subquery()
    )

    has_current_drill = exists(
        select(1).where(
            RecoveryDrillRun.organization_id == scopes.c.organization_id,
            RecoveryDrillRun.program_id == scopes.c.program_id,
            RecoveryDrillRun.event_id == scopes.c.event_id,
            RecoveryDrillRun.store_id == scopes.c.store_id,
            RecoveryDrillRun.performed_at >= cutoff,
        )
    )

    count = db.scalar(select(func.count()).select_from(scopes).where(~has_current_drill))
    return int(count or 0)
