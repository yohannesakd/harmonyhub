from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, text

from app.config import WorkerSettings
from app.jobs import build_scheduler, operations_compliance_job


def _build_minimal_operations_schema(database_url: str) -> None:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS memberships (
                    organization_id TEXT NOT NULL,
                    program_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    store_id TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS recovery_drill_runs (
                    organization_id TEXT NOT NULL,
                    program_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    store_id TEXT NOT NULL,
                    performed_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )


def test_operations_compliance_job_prunes_old_audit_events_and_counts_overdue_scopes(tmp_path):
    db_path = tmp_path / "worker_ops.db"
    database_url = f"sqlite+pysqlite:///{db_path}"
    _build_minimal_operations_schema(database_url)

    now = datetime.now(UTC)
    old_timestamp = now - timedelta(days=400)
    current_timestamp = now - timedelta(days=10)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO memberships (organization_id, program_id, event_id, store_id) VALUES "
                "('org-1','prog-1','event-1','store-1'),"
                "('org-2','prog-2','event-2','store-2')"
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO recovery_drill_runs (organization_id, program_id, event_id, store_id, performed_at)
                VALUES ('org-1','prog-1','event-1','store-1', :performed_at)
                """
            ),
            {"performed_at": now - timedelta(days=30)},
        )
        connection.execute(
            text(
                """
                INSERT INTO audit_events (id, created_at)
                VALUES ('audit-old', :old_created_at), ('audit-current', :current_created_at)
                """
            ),
            {"old_created_at": old_timestamp, "current_created_at": current_timestamp},
        )

    summary = operations_compliance_job(
        database_url,
        audit_retention_days=365,
        recovery_drill_interval_days=90,
    )

    assert summary["deleted_audit_events"] == 1
    assert summary["overdue_recovery_drill_scopes"] == 1

    with engine.begin() as connection:
        remaining = connection.execute(text("SELECT COUNT(*) FROM audit_events")).scalar_one()
    assert remaining == 1


def test_scheduler_registers_expected_jobs():
    settings = WorkerSettings(
        DATABASE_URL="sqlite+pysqlite:///./worker_test.db",
        HH_WORKER_HEARTBEAT_SECONDS=10,
        HH_WORKER_BACKUP_CHECK_SECONDS=60,
        HH_WORKER_OPERATIONS_CHECK_SECONDS=120,
        HH_AUDIT_RETENTION_DAYS=365,
        HH_RECOVERY_DRILL_INTERVAL_DAYS=90,
    )
    scheduler = build_scheduler(settings)

    jobs = scheduler.get_jobs()
    job_ids = {job.id for job in jobs}

    assert "heartbeat" in job_ids
    assert "backup-medium-probe" in job_ids
    assert "operations-compliance" in job_ids
