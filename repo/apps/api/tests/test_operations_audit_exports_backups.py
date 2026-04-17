from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.field_encryption import decrypt_bytes
from app.db.base import Base
from app.db.models import AuditEvent, ExportRun, Membership, RecoveryDrillRun, User
from app.db.init_data import seed_baseline_data
from app.db.session import get_engine
from app.main import create_app
from app.operations.compliance import prune_audit_events_for_retention


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _headers(csrf: str, nonce: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": csrf,
        "X-Request-Nonce": nonce,
        "X-Request-Timestamp": _iso_now(),
    }


def _login(client, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_operations_permission_boundaries_for_student_role(client):
    student_csrf = _login(client, "student", "stud123!")

    status = client.get("/api/v1/operations/status")
    assert status.status_code == 403
    assert status.json()["error"]["code"] == "FORBIDDEN"

    export = client.post(
        "/api/v1/operations/exports/directory-csv",
        headers=_headers(student_csrf, nonce="student-export-denied"),
        json={"include_sensitive": False},
    )
    assert export.status_code == 403
    assert export.json()["error"]["code"] == "FORBIDDEN"


def test_directory_export_masks_sensitive_fields_and_records_audit(client):
    staff_csrf = _login(client, "staff", "staff123!")

    export = client.post(
        "/api/v1/operations/exports/directory-csv",
        headers=_headers(staff_csrf, nonce="staff-export-masked"),
        json={"include_sensitive": False},
    )
    assert export.status_code == 200
    payload = export.json()
    run_id = payload["export_run"]["id"]

    runs = client.get("/api/v1/operations/exports/runs")
    assert runs.status_code == 200
    run_rows = runs.json()
    assert any(row["id"] == run_id for row in run_rows)

    with Session(get_engine()) as session:
        run = session.scalar(select(ExportRun).where(ExportRun.id == run_id))
        assert run is not None
        encrypted_artifact = Path(run.file_path).read_bytes()
        assert encrypted_artifact.startswith(b"enc::")
        assert b"display_name" not in encrypted_artifact

        decrypted_artifact = decrypt_bytes(encrypted_artifact).decode("utf-8")
        assert "display_name" in decrypted_artifact

    downloaded = client.get(payload["download_path"])
    assert downloaded.status_code == 200
    csv_text = downloaded.content.decode("utf-8")
    parsed = list(csv.DictReader(io.StringIO(csv_text)))
    assert parsed
    first = parsed[0]
    assert "***" in first["email"]
    assert first["email"] != "ava.martinez@harmonyhub.example"
    assert "***" in first["phone"]
    assert first["address_line1"] == "*** Hidden address ***"

    with Session(get_engine()) as session:
        events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.target_type == "export_run",
                AuditEvent.target_id == run_id,
                AuditEvent.action.in_(["exports.directory.generated", "exports.directory.downloaded"]),
            )
        ).all()
        actions = {event.action for event in events}
        assert "exports.directory.generated" in actions
        assert "exports.directory.downloaded" in actions


def test_export_download_rejects_artifact_outside_export_directory(client, tmp_path):
    staff_csrf = _login(client, "staff", "staff123!")

    export = client.post(
        "/api/v1/operations/exports/directory-csv",
        headers=_headers(staff_csrf, nonce="staff-export-outside-dir"),
        json={"include_sensitive": False},
    )
    assert export.status_code == 200
    run_id = export.json()["export_run"]["id"]

    tampered = tmp_path / "outside.csv"
    tampered.write_text("id,name\n1,outside\n", encoding="utf-8")

    with Session(get_engine()) as session:
        run = session.scalar(select(ExportRun).where(ExportRun.id == run_id))
        assert run is not None
        run.file_path = str(tampered)
        session.add(run)
        session.commit()

    downloaded = client.get(f"/api/v1/operations/exports/runs/{run_id}/download")
    assert downloaded.status_code == 404
    assert downloaded.json()["error"]["code"] == "VALIDATION_ERROR"


def test_export_runs_are_requester_scoped_for_listing_and_download(client):
    staff_csrf = _login(client, "staff", "staff123!")
    export = client.post(
        "/api/v1/operations/exports/directory-csv",
        headers=_headers(staff_csrf, nonce="staff-export-requester-scope"),
        json={"include_sensitive": False},
    )
    assert export.status_code == 200
    run_id = export.json()["export_run"]["id"]

    _login(client, "admin", "admin123!")
    listed = client.get("/api/v1/operations/exports/runs")
    assert listed.status_code == 200
    assert all(row["id"] != run_id for row in listed.json())

    downloaded = client.get(f"/api/v1/operations/exports/runs/{run_id}/download")
    assert downloaded.status_code == 404
    assert downloaded.json()["error"]["code"] == "VALIDATION_ERROR"


def test_backups_recovery_drills_and_operations_status(client):
    staff_csrf = _login(client, "staff", "staff123!")

    backup = client.post(
        "/api/v1/operations/backups/run",
        headers=_headers(staff_csrf, nonce="manual-backup"),
        json={"copy_to_offline_medium": True},
    )
    assert backup.status_code == 200
    backup_payload = backup.json()
    backup_id = backup_payload["id"]
    assert backup_payload["status"] == "completed"
    assert backup_payload["offline_copy_verified"] is True
    assert backup_payload["verification_json"]["checksum_algorithm"] == "sha256"
    assert backup_payload["verification_json"]["backup_kind"] == "tenant_logical_full"
    assert backup_payload["verification_json"]["backup_format_version"] == 2
    assert "orders" in backup_payload["verification_json"]["table_counts"]
    assert backup_payload["verification_json"]["table_counts"]["menu_items"] >= 1
    assert backup_payload["verification_json"]["table_counts"]["memberships"] >= 1

    backup_file = Path(backup_payload["file_path"])
    assert backup_file.exists()
    encrypted_backup_artifact = backup_file.read_bytes()
    assert encrypted_backup_artifact.startswith(b"enc::")
    assert b'"backup_kind"' not in encrypted_backup_artifact

    backup_artifact = json.loads(decrypt_bytes(encrypted_backup_artifact).decode("utf-8"))
    assert backup_artifact["backup_kind"] == "tenant_logical_full"
    assert backup_artifact["backup_format_version"] == 2
    assert "tables" in backup_artifact
    for table_name in ["orders", "order_items", "memberships", "menu_items", "import_batches", "audit_events"]:
        assert table_name in backup_artifact["tables"]

    assert backup_payload["offline_copy_path"]
    offline_copy_artifact = Path(backup_payload["offline_copy_path"])
    assert offline_copy_artifact.exists()
    encrypted_offline_copy = offline_copy_artifact.read_bytes()
    assert encrypted_offline_copy.startswith(b"enc::")
    assert decrypt_bytes(encrypted_offline_copy) == decrypt_bytes(encrypted_backup_artifact)

    listed_backups = client.get("/api/v1/operations/backups/runs")
    assert listed_backups.status_code == 200
    assert any(row["id"] == backup_id for row in listed_backups.json())

    drill = client.post(
        "/api/v1/operations/recovery-drills",
        headers=_headers(staff_csrf, nonce="record-drill"),
        json={
            "backup_run_id": backup_id,
            "scenario": "restore-latest-and-verify-order-count",
            "status": "passed",
            "evidence_json": {"notes": "restored to isolated environment"},
            "notes": "Verified order records available after restore.",
        },
    )
    assert drill.status_code == 200
    drill_payload = drill.json()
    assert drill_payload["backup_run_id"] == backup_id
    assert drill_payload["status"] == "passed"
    assert drill_payload["evidence_json"]["restore"]["status"] == "completed"
    assert drill_payload["evidence_json"]["restore"]["table_counts_match"] is True
    assert drill_payload["evidence_json"]["restore"]["restore_target"] in {
        "isolated_postgres_schema",
        "isolated_sqlite_database",
    }

    restore_summary = drill_payload["evidence_json"]["restore"]
    expected_counts = drill_payload["evidence_json"]["restore"]["expected_table_counts"]

    if restore_summary["restore_target"] == "isolated_sqlite_database":
        restored_db_path = Path(restore_summary["restore_database_path"])
        assert restored_db_path.exists()
        with sqlite3.connect(restored_db_path) as connection:
            restored_orders = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            restored_menu_items = connection.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
    else:
        restore_schema = restore_summary["restore_schema"]
        restore_engine = create_engine(get_settings().database_url)
        with restore_engine.connect() as connection:
            restored_orders = connection.execute(text(f'SELECT COUNT(*) FROM "{restore_schema}"."orders"')).scalar_one()
            restored_menu_items = connection.execute(text(f'SELECT COUNT(*) FROM "{restore_schema}"."menu_items"')).scalar_one()

    assert restored_orders == expected_counts["orders"]
    assert restored_menu_items == expected_counts["menu_items"]
    assert restored_menu_items >= 1

    listed_drills = client.get("/api/v1/operations/recovery-drills")
    assert listed_drills.status_code == 200
    assert any(row["id"] == drill_payload["id"] for row in listed_drills.json())

    status = client.get("/api/v1/operations/status")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["latest_backup"] is not None
    assert status_payload["latest_backup"]["id"] == backup_id
    assert status_payload["latest_recovery_drill"] is not None
    assert status_payload["latest_recovery_drill"]["id"] == drill_payload["id"]
    assert status_payload["audit_retention"]["retention_days"] == 365
    assert status_payload["audit_retention"]["events_older_than_retention"] == 0
    assert status_payload["recovery_drill_compliance"]["status"] == "current"
    assert status_payload["recovery_drill_compliance"]["interval_days"] == 90


def test_operations_status_reports_recovery_drill_overdue_when_no_drill_recorded(client):
    _login(client, "staff", "staff123!")
    status = client.get("/api/v1/operations/status")
    assert status.status_code == 200
    compliance = status.json()["recovery_drill_compliance"]
    assert compliance["status"] == "overdue"
    assert compliance["latest_performed_at"] is None


def test_recovery_drill_uses_postgres_restore_schema_when_running_on_postgres(monkeypatch):
    postgres_url = os.getenv("HH_TEST_POSTGRES_DATABASE_URL", "").strip()
    if not postgres_url:
        pytest.skip("PostgreSQL drill test requires HH_TEST_POSTGRES_DATABASE_URL")

    try:
        probe_engine = create_engine(postgres_url, pool_pre_ping=True)
        with probe_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL drill test unavailable: {exc}")

    monkeypatch.setenv("DATABASE_URL", postgres_url)
    monkeypatch.setenv("HH_COOKIE_SECURE", "false")
    get_settings.cache_clear()

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_baseline_data(session)

    with TestClient(create_app(), client=("198.51.100.55", 51000)) as postgres_client:
        staff_csrf = _login(postgres_client, "staff", "staff123!")
        backup = postgres_client.post(
            "/api/v1/operations/backups/run",
            headers=_headers(staff_csrf, nonce="postgres-restore-backup"),
            json={"copy_to_offline_medium": False},
        )
        assert backup.status_code == 200
        backup_run_id = backup.json()["id"]

        drill = postgres_client.post(
            "/api/v1/operations/recovery-drills",
            headers=_headers(staff_csrf, nonce="postgres-restore-drill"),
            json={
                "backup_run_id": backup_run_id,
                "scenario": "postgres-restore-path-verification",
                "status": "passed",
            },
        )
        assert drill.status_code == 200
        restore = drill.json()["evidence_json"]["restore"]
        assert restore["restore_target"] == "isolated_postgres_schema"
        assert restore["restore_dialect"].startswith("postgres")
        assert restore["table_counts_match"] is True
        assert isinstance(restore.get("restore_schema"), str)


def test_recovery_drill_records_failed_status_when_backup_artifact_is_tampered(client):
    staff_csrf = _login(client, "staff", "staff123!")
    backup = client.post(
        "/api/v1/operations/backups/run",
        headers=_headers(staff_csrf, nonce="manual-backup-for-tamper"),
        json={"copy_to_offline_medium": False},
    )
    assert backup.status_code == 200
    backup_payload = backup.json()

    backup_path = Path(backup_payload["file_path"])
    assert backup_path.exists()
    backup_path.write_text('{"tampered":true}', encoding="utf-8")

    drill = client.post(
        "/api/v1/operations/recovery-drills",
        headers=_headers(staff_csrf, nonce="tampered-drill"),
        json={
            "backup_run_id": backup_payload["id"],
            "scenario": "restore-from-tampered-artifact",
            "status": "passed",
        },
    )
    assert drill.status_code == 200
    drill_payload = drill.json()
    assert drill_payload["status"] == "failed"
    assert drill_payload["evidence_json"]["restore"]["status"] == "failed"
    restore_error = drill_payload["evidence_json"]["restore"].get("error")
    assert isinstance(restore_error, dict)
    assert restore_error.get("exception_type") == "ValueError"
    assert isinstance(drill_payload.get("notes"), str)
    assert "Restore drill failed:" in drill_payload["notes"]


def test_audit_retention_prunes_events_older_than_12_months():
    with Session(get_engine()) as session:
        user = session.scalar(select(User).where(User.username == "staff"))
        assert user is not None
        membership = session.scalar(
            select(Membership)
            .where(Membership.user_id == user.id)
            .order_by(Membership.created_at.asc())
        )
        assert membership is not None

        stale = AuditEvent(
            organization_id=membership.organization_id,
            program_id=membership.program_id,
            event_id=membership.event_id,
            store_id=membership.store_id,
            actor_user_id=user.id,
            actor_role=membership.role,
            action="retention.test.stale",
            target_type="retention_probe",
            target_id="stale",
            details_json={"marker": "stale"},
            created_at=datetime.now(UTC) - timedelta(days=400),
        )
        fresh = AuditEvent(
            organization_id=membership.organization_id,
            program_id=membership.program_id,
            event_id=membership.event_id,
            store_id=membership.store_id,
            actor_user_id=user.id,
            actor_role=membership.role,
            action="retention.test.fresh",
            target_type="retention_probe",
            target_id="fresh",
            details_json={"marker": "fresh"},
            created_at=datetime.now(UTC) - timedelta(days=20),
        )
        session.add_all([stale, fresh])
        session.commit()

        deleted = prune_audit_events_for_retention(session, retention_days=365)
        session.commit()
        assert deleted >= 1

        remaining_actions = set(
            session.scalars(
                select(AuditEvent.action).where(AuditEvent.action.like("retention.test.%"))
            ).all()
        )
        assert "retention.test.stale" not in remaining_actions
        assert "retention.test.fresh" in remaining_actions


def test_operations_status_reports_recovery_drill_overdue_when_last_drill_is_stale(client):
    staff_csrf = _login(client, "staff", "staff123!")
    drill = client.post(
        "/api/v1/operations/recovery-drills",
        headers=_headers(staff_csrf, nonce="record-overdue-drill"),
        json={
            "scenario": "stale-drill-for-overdue-check",
            "status": "passed",
        },
    )
    assert drill.status_code == 200
    drill_payload = drill.json()
    drill_id = drill_payload["id"]
    assert drill_payload["backup_run_id"] is not None
    assert drill_payload["evidence_json"]["restore"]["status"] == "completed"

    with Session(get_engine()) as session:
        run = session.scalar(select(RecoveryDrillRun).where(RecoveryDrillRun.id == drill_id))
        assert run is not None
        run.performed_at = datetime.now(UTC) - timedelta(days=120)
        session.add(run)
        session.commit()

    status = client.get("/api/v1/operations/status")
    assert status.status_code == 200
    compliance = status.json()["recovery_drill_compliance"]
    assert compliance["status"] == "overdue"
    assert compliance["days_overdue"] >= 1


def test_audit_events_support_filters_and_redaction(client):
    _login(client, "staff", "staff123!")

    with Session(get_engine()) as session:
        user = session.scalar(select(User).where(User.username == "staff"))
        assert user is not None
        membership = session.scalar(
            select(Membership)
            .where(Membership.user_id == user.id)
            .order_by(Membership.created_at.asc())
        )
        assert membership is not None

        event = AuditEvent(
            organization_id=membership.organization_id,
            program_id=membership.program_id,
            event_id=membership.event_id,
            store_id=membership.store_id,
            actor_user_id=user.id,
            actor_role=membership.role,
            action="security.test.redaction",
            target_type="security_probe",
            target_id="probe-1",
            details_json={
                "code": "123456",
                "email": "leak@example.com",
                "phone": "555-444-0000",
                "address_line1": "100 Private Lane",
                "nested": {
                    "password": "plain",
                    "safe": "ok",
                    "contact_email": "nested@example.com",
                },
            },
        )
        session.add(event)
        session.commit()

    audit_rows = client.get(
        "/api/v1/operations/audit-events",
        params={"action_prefix": "security.", "target_type": "security_probe", "limit": 10},
    )
    assert audit_rows.status_code == 200
    rows = audit_rows.json()
    assert len(rows) == 1
    details = rows[0]["details_json"]
    assert details["code"] == "***REDACTED***"
    assert details["email"] == "***REDACTED***"
    assert details["phone"] == "***REDACTED***"
    assert details["address_line1"] == "***REDACTED***"
    assert details["nested"]["password"] == "***REDACTED***"
    assert details["nested"]["contact_email"] == "***REDACTED***"
    assert details["nested"]["safe"] == "ok"


def test_auth_and_policy_changes_emit_audit_events(client):
    bad_login = client.post("/api/v1/auth/login", json={"username": "staff", "password": "bad-password"})
    assert bad_login.status_code == 401

    admin_csrf = _login(client, "admin", "admin123!")
    upsert_surface = client.put(
        "/api/v1/admin/policies/abac/surfaces/operations",
        headers=_headers(admin_csrf, nonce="policy-upsert-operations"),
        json={"enabled": True},
    )
    assert upsert_surface.status_code == 200

    _login(client, "staff", "staff123!")

    with Session(get_engine()) as session:
        staff_user = session.scalar(select(User).where(User.username == "staff"))
        assert staff_user is not None
        auth_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.actor_user_id == staff_user.id,
                AuditEvent.action.in_(["auth.login.failed", "auth.login.succeeded"]),
            )
        ).all()
        auth_actions = {event.action for event in auth_events}
        assert "auth.login.failed" in auth_actions
        assert "auth.login.succeeded" in auth_actions

        policy_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "policy.abac.surface.upsert",
                AuditEvent.target_type == "abac_surface",
            )
        ).all()
        assert policy_events

        upsert_details = policy_events[0].details_json or {}
        assert upsert_details.get("surface") == "operations"
        assert upsert_details.get("enabled") is True
