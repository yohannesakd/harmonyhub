from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine, text

from app.config import WorkerSettings

logger = logging.getLogger(__name__)


def heartbeat_job(database_url: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    logger.info("Worker heartbeat OK", extra={"job": "heartbeat"})


def backup_medium_probe_job(offline_medium_path: str) -> None:
    target = Path(offline_medium_path)
    target.mkdir(parents=True, exist_ok=True)
    probe_file = target / ".probe"
    probe_file.write_text("harmonyhub-worker-probe", encoding="utf-8")
    logger.info(
        "Offline backup medium probe complete",
        extra={"job": "backup_medium_probe", "path": str(target)},
    )


def operations_compliance_job(
    database_url: str,
    *,
    audit_retention_days: int,
    recovery_drill_interval_days: int,
) -> dict[str, int]:
    now = datetime.now(UTC)
    retention_cutoff = now - timedelta(days=audit_retention_days)
    drill_freshness_cutoff = now - timedelta(days=recovery_drill_interval_days)

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        deleted = connection.execute(
            text("DELETE FROM audit_events WHERE created_at < :cutoff"),
            {"cutoff": retention_cutoff},
        ).rowcount or 0

        overdue_scopes = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                  SELECT DISTINCT organization_id, program_id, event_id, store_id
                  FROM memberships
                ) AS scopes
                WHERE NOT EXISTS (
                  SELECT 1
                  FROM recovery_drill_runs d
                  WHERE d.organization_id = scopes.organization_id
                    AND d.program_id = scopes.program_id
                    AND d.event_id = scopes.event_id
                    AND d.store_id = scopes.store_id
                    AND d.performed_at >= :drill_freshness_cutoff
                )
                """
            ),
            {"drill_freshness_cutoff": drill_freshness_cutoff},
        ).scalar_one()

    summary = {
        "deleted_audit_events": int(deleted),
        "overdue_recovery_drill_scopes": int(overdue_scopes),
    }

    logger.info(
        "Operations compliance check complete",
        extra={
            "job": "operations_compliance",
            "audit_retention_days": audit_retention_days,
            "recovery_drill_interval_days": recovery_drill_interval_days,
            **summary,
        },
    )
    return summary


def build_scheduler(settings: WorkerSettings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(heartbeat_job, "interval", seconds=settings.heartbeat_seconds, args=[settings.database_url], id="heartbeat")
    scheduler.add_job(
        backup_medium_probe_job,
        "interval",
        seconds=settings.backup_check_seconds,
        args=[settings.offline_backup_medium_path],
        id="backup-medium-probe",
    )
    scheduler.add_job(
        operations_compliance_job,
        "interval",
        seconds=settings.operations_check_seconds,
        kwargs={
            "database_url": settings.database_url,
            "audit_retention_days": settings.audit_retention_days,
            "recovery_drill_interval_days": settings.recovery_drill_interval_days,
        },
        id="operations-compliance",
    )
    return scheduler
