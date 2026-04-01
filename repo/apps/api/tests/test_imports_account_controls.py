from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.imports.security import MAX_UPLOAD_BYTES
from app.main import create_app
from app.core.security import hash_password
from app.db.models import AuditEvent, DirectoryEntry, DirectoryEntryRepertoireItem, ImportBatch, Membership, UploadedAsset, User
from app.db.session import get_engine


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


def _upload_member_batch(client, csrf: str, csv_bytes: bytes):
    return client.post(
        "/api/v1/imports/batches/upload",
        data={"kind": "member"},
        files={"file": ("members.csv", csv_bytes, "text/csv")},
        headers=_headers(csrf, nonce=f"upload-member-{datetime.now(UTC).timestamp()}"),
    )


def _upload_roster_batch(client, csrf: str, csv_bytes: bytes):
    return client.post(
        "/api/v1/imports/batches/upload",
        data={"kind": "roster"},
        files={"file": ("roster.csv", csv_bytes, "text/csv")},
        headers=_headers(csrf, nonce=f"upload-roster-{datetime.now(UTC).timestamp()}"),
    )


def test_upload_rejects_invalid_extension_mime_magic_and_size(client):
    staff_csrf = _login(client, "staff", "staff123!")

    bad_ext = client.post(
        "/api/v1/uploads",
        files={"file": ("payload.exe", b"evil", "application/octet-stream")},
        headers=_headers(staff_csrf, nonce="upload-bad-ext"),
    )
    assert bad_ext.status_code == 422
    assert bad_ext.json()["error"]["code"] == "UPLOAD_REJECTED"

    bad_mime = client.post(
        "/api/v1/uploads",
        files={"file": ("image.png", b"\x89PNG\r\n\x1a\nabc", "image/jpeg")},
        headers=_headers(staff_csrf, nonce="upload-bad-mime"),
    )
    assert bad_mime.status_code == 422
    assert bad_mime.json()["error"]["code"] == "UPLOAD_REJECTED"

    bad_magic = client.post(
        "/api/v1/uploads",
        files={"file": ("report.pdf", b"name,email\nAva,ava@example.com\n", "application/pdf")},
        headers=_headers(staff_csrf, nonce="upload-bad-magic"),
    )
    assert bad_magic.status_code == 422
    assert bad_magic.json()["error"]["code"] == "UPLOAD_REJECTED"

    too_large = client.post(
        "/api/v1/uploads",
        files={"file": ("huge.csv", b"a,b\n" + (b"x" * (MAX_UPLOAD_BYTES + 1)), "text/csv")},
        headers=_headers(staff_csrf, nonce="upload-too-large"),
    )
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "UPLOAD_REJECTED"


def test_upload_persists_sha256_and_raw_preservation(client):
    staff_csrf = _login(client, "staff", "staff123!")
    raw_csv = b"display_name,email,region\nCasey Import,casey@example.com,North Region\n"

    uploaded = _upload_member_batch(client, staff_csrf, raw_csv)
    assert uploaded.status_code == 200
    payload = uploaded.json()
    upload_meta = payload["upload"]
    expected_sha = hashlib.sha256(raw_csv).hexdigest()
    assert upload_meta["sha256"] == expected_sha

    with Session(get_engine()) as session:
        stored = session.scalar(select(UploadedAsset).where(UploadedAsset.id == upload_meta["id"]))
        assert stored is not None
        assert stored.sha256 == expected_sha
        assert stored.raw_bytes == raw_csv


def test_member_csv_normalize_and_apply_outcomes(client):
    staff_csrf = _login(client, "staff", "staff123!")
    raw_csv = (
        b"display_name,email,region,phone\n"
        b"Taylor Imported,taylor@example.com,North Region,555-000-1212\n"
        b",missing@example.com,North Region,555-999-9999\n"
    )

    uploaded = _upload_member_batch(client, staff_csrf, raw_csv)
    assert uploaded.status_code == 200
    batch_id = uploaded.json()["batch"]["id"]

    normalized = client.post(
        f"/api/v1/imports/batches/{batch_id}/normalize",
        headers=_headers(staff_csrf, nonce="normalize-member-batch"),
    )
    assert normalized.status_code == 200
    normalized_payload = normalized.json()
    assert normalized_payload["total_rows"] == 2
    assert normalized_payload["valid_rows"] == 1
    assert normalized_payload["issue_count"] >= 1

    applied = client.post(
        f"/api/v1/imports/batches/{batch_id}/apply",
        headers=_headers(staff_csrf, nonce="apply-member-batch"),
    )
    assert applied.status_code == 200
    assert applied.json()["status"] == "processed"

    with Session(get_engine()) as session:
        imported = session.scalar(select(DirectoryEntry).where(DirectoryEntry.display_name == "Taylor Imported"))
        assert imported is not None
        assert imported.email == "taylor@example.com"


def test_roster_csv_normalize_and_apply_creates_links(client):
    staff_csrf = _login(client, "staff", "staff123!")
    raw_csv = b"performer_name,repertoire_title,composer,region\nRowan Link,Sunrise Prelude,L. Gray,West Region\n"
    uploaded = _upload_roster_batch(client, staff_csrf, raw_csv)
    assert uploaded.status_code == 200
    batch_id = uploaded.json()["batch"]["id"]

    assert (
        client.post(
            f"/api/v1/imports/batches/{batch_id}/normalize",
            headers=_headers(staff_csrf, nonce="normalize-roster-batch"),
        ).status_code
        == 200
    )
    applied = client.post(
        f"/api/v1/imports/batches/{batch_id}/apply",
        headers=_headers(staff_csrf, nonce="apply-roster-batch"),
    )
    assert applied.status_code == 200
    assert applied.json()["status"] == "processed"

    with Session(get_engine()) as session:
        performer = session.scalar(select(DirectoryEntry).where(DirectoryEntry.display_name == "Rowan Link"))
        assert performer is not None
        repertoire = session.scalar(select(ImportBatch).where(ImportBatch.id == batch_id))
        assert repertoire is not None
        links = session.scalars(
            select(DirectoryEntryRepertoireItem).where(DirectoryEntryRepertoireItem.directory_entry_id == performer.id)
        ).all()
        assert links


def test_duplicate_detection_merge_and_safe_undo(client):
    staff_csrf = _login(client, "staff", "staff123!")

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    active_context = me.json()["active_context"]

    with Session(get_engine()) as session:
        existing = DirectoryEntry(
            organization_id=active_context["organization_id"],
            program_id=active_context["program_id"],
            event_id=active_context["event_id"],
            store_id=active_context["store_id"],
            display_name="Merge Candidate",
            stage_name=None,
            region="North Region",
            email=None,
            phone=None,
            address_line1=None,
            biography=None,
        )
        session.add(existing)
        session.commit()
        target_id = existing.id

    raw_csv = b"display_name,phone,region\nMerge Candidate,555-101-2020,North Region\n"
    uploaded = _upload_member_batch(client, staff_csrf, raw_csv)
    assert uploaded.status_code == 200
    batch_id = uploaded.json()["batch"]["id"]

    normalized = client.post(
        f"/api/v1/imports/batches/{batch_id}/normalize",
        headers=_headers(staff_csrf, nonce="normalize-dup-batch"),
    )
    assert normalized.status_code == 200
    assert normalized.json()["duplicate_count"] == 1

    duplicates = client.get("/api/v1/imports/duplicates?status=open")
    assert duplicates.status_code == 200
    duplicate = next(row for row in duplicates.json() if row["batch_id"] == batch_id)
    assert duplicate["target_directory_entry_id"] == target_id

    merged = client.post(
        f"/api/v1/imports/duplicates/{duplicate['id']}/merge",
        headers=_headers(staff_csrf, nonce="merge-duplicate"),
        json={"note": "merge phone from import"},
    )
    assert merged.status_code == 200
    merge_action_id = merged.json()["merge_action_id"]

    with Session(get_engine()) as session:
        target = session.scalar(select(DirectoryEntry).where(DirectoryEntry.id == target_id))
        assert target is not None
        assert target.phone == "555-101-2020"

        merge_audit = session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.action == "imports.duplicate.merged",
                AuditEvent.target_id == duplicate["id"],
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert merge_audit is not None
        details = merge_audit.details_json or {}
        applied = details.get("applied_changes") or {}
        applied_fields = applied.get("fields") if isinstance(applied, dict) else {}
        # Imported contact fields must not be persisted in plaintext in audit details.
        assert isinstance(applied_fields, dict)
        assert applied_fields.get("phone") == "***REDACTED***"

    undone = client.post(
        f"/api/v1/imports/merges/{merge_action_id}/undo",
        headers=_headers(staff_csrf, nonce="undo-merge"),
        json={"reason": "operator requested rollback"},
    )
    assert undone.status_code == 200

    with Session(get_engine()) as session:
        target = session.scalar(select(DirectoryEntry).where(DirectoryEntry.id == target_id))
        assert target is not None
        assert target.phone is None


def test_freeze_unfreeze_enforces_protected_usage_and_records_audit(client):
    referee_csrf = _login(client, "referee", "ref123!")
    assert referee_csrf

    with TestClient(create_app()) as staff_client:
        staff_csrf = _login(staff_client, "staff", "staff123!")
        users = staff_client.get("/api/v1/accounts/users")
        assert users.status_code == 200
        referee_user = next(user for user in users.json() if user["username"] == "referee")

        frozen = staff_client.post(
            f"/api/v1/accounts/users/{referee_user['id']}/freeze",
            headers=_headers(staff_csrf, nonce="freeze-referee"),
            json={"reason": "Policy hold"},
        )
        assert frozen.status_code == 200
        assert frozen.json()["is_frozen"] is True

    blocked = client.get("/api/v1/dashboard/event")
    assert blocked.status_code == 423
    assert blocked.json()["error"]["code"] == "ACCOUNT_FROZEN"
    assert "reason" not in blocked.json()["error"]["details"]

    login_again = client.post("/api/v1/auth/login", json={"username": "referee", "password": "ref123!"})
    assert login_again.status_code == 423
    assert login_again.json()["error"]["code"] == "ACCOUNT_FROZEN"
    assert "reason" not in login_again.json()["error"]["details"]

    with TestClient(create_app()) as staff_client:
        staff_csrf = _login(staff_client, "staff", "staff123!")
        users = staff_client.get("/api/v1/accounts/users")
        referee_user = next(user for user in users.json() if user["username"] == "referee")

        unfrozen = staff_client.post(
            f"/api/v1/accounts/users/{referee_user['id']}/unfreeze",
            headers=_headers(staff_csrf, nonce="unfreeze-referee"),
            json={"reason": "Cleared"},
        )
        assert unfrozen.status_code == 200
        assert unfrozen.json()["is_frozen"] is False

    login_ok = client.post("/api/v1/auth/login", json={"username": "referee", "password": "ref123!"})
    assert login_ok.status_code == 200

    with Session(get_engine()) as session:
        referee = session.scalar(select(User).where(User.username == "referee"))
        assert referee is not None
        events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.target_type == "user",
                AuditEvent.target_id == referee.id,
                AuditEvent.action.in_(["account.freeze", "account.unfreeze"]),
            )
        ).all()
        actions = {event.action for event in events}
        assert "account.freeze" in actions
        assert "account.unfreeze" in actions


def test_account_controls_are_scoped_to_active_context(client):
    with TestClient(create_app()) as staff_client:
        staff_csrf = _login(staff_client, "staff", "staff123!")
        me = staff_client.get("/api/v1/auth/me")
        assert me.status_code == 200
        active_context = me.json()["active_context"]
        assert active_context is not None

        with Session(get_engine()) as session:
            staff = session.scalar(select(User).where(User.username == "staff"))
            assert staff is not None

            same_org_staff_memberships = session.scalars(
                select(Membership)
                .where(
                    Membership.user_id == staff.id,
                    Membership.organization_id == active_context["organization_id"],
                )
                .order_by(Membership.created_at.asc())
            ).all()

            out_of_scope_membership = next(
                (
                    membership
                    for membership in same_org_staff_memberships
                    if (
                        membership.program_id,
                        membership.event_id,
                        membership.store_id,
                    )
                    != (
                        active_context["program_id"],
                        active_context["event_id"],
                        active_context["store_id"],
                    )
                ),
                None,
            )
            assert out_of_scope_membership is not None

            outsider = User(
                username=f"outsider-{uuid.uuid4().hex[:8]}",
                password_hash=hash_password("outsider-temp-pass"),
                is_active=True,
            )
            session.add(outsider)
            session.flush()

            session.add(
                Membership(
                    user_id=outsider.id,
                    organization_id=out_of_scope_membership.organization_id,
                    program_id=out_of_scope_membership.program_id,
                    event_id=out_of_scope_membership.event_id,
                    store_id=out_of_scope_membership.store_id,
                    role="student",
                )
            )
            session.commit()
            outsider_user_id = outsider.id
            outsider_username = outsider.username

        listed = staff_client.get("/api/v1/accounts/users")
        assert listed.status_code == 200
        usernames = {row["username"] for row in listed.json()}
        assert outsider_username not in usernames

        freeze_outsider = staff_client.post(
            f"/api/v1/accounts/users/{outsider_user_id}/freeze",
            headers=_headers(staff_csrf, nonce="freeze-outsider-out-of-context"),
            json={"reason": "should not be allowed"},
        )
        assert freeze_outsider.status_code == 404
        assert freeze_outsider.json()["error"]["code"] == "VALIDATION_ERROR"

        unfreeze_outsider = staff_client.post(
            f"/api/v1/accounts/users/{outsider_user_id}/unfreeze",
            headers=_headers(staff_csrf, nonce="unfreeze-outsider-out-of-context"),
            json={"reason": "should not be allowed"},
        )
        assert unfreeze_outsider.status_code == 404
        assert unfreeze_outsider.json()["error"]["code"] == "VALIDATION_ERROR"


def test_import_listing_detail_and_duplicate_ignore_path(client):
    staff_csrf = _login(client, "staff", "staff123!")

    upload_asset = client.post(
        "/api/v1/uploads",
        files={"file": ("proof.csv", b"a,b\n1,2\n", "text/csv")},
        headers=_headers(staff_csrf, nonce="upload-listing-asset"),
    )
    assert upload_asset.status_code == 200

    uploads = client.get("/api/v1/uploads")
    assert uploads.status_code == 200
    assert any(row["id"] == upload_asset.json()["id"] for row in uploads.json())

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    active_context = me.json()["active_context"]

    with Session(get_engine()) as session:
        existing = DirectoryEntry(
            organization_id=active_context["organization_id"],
            program_id=active_context["program_id"],
            event_id=active_context["event_id"],
            store_id=active_context["store_id"],
            display_name="Ignore Candidate",
            stage_name=None,
            region="North Region",
            email=None,
            phone=None,
            address_line1=None,
            biography=None,
        )
        session.add(existing)
        session.commit()

    raw_csv = b"display_name,phone,region\nIgnore Candidate,555-000-9999,North Region\n"
    uploaded_batch = _upload_member_batch(client, staff_csrf, raw_csv)
    assert uploaded_batch.status_code == 200
    batch_id = uploaded_batch.json()["batch"]["id"]

    list_batches = client.get("/api/v1/imports/batches")
    assert list_batches.status_code == 200
    assert any(row["id"] == batch_id for row in list_batches.json())

    batch_detail = client.get(f"/api/v1/imports/batches/{batch_id}")
    assert batch_detail.status_code == 200
    assert batch_detail.json()["batch"]["id"] == batch_id

    normalized = client.post(
        f"/api/v1/imports/batches/{batch_id}/normalize",
        headers=_headers(staff_csrf, nonce="normalize-ignore-batch"),
    )
    assert normalized.status_code == 200
    assert normalized.json()["duplicate_count"] == 1

    duplicates = client.get("/api/v1/imports/duplicates", params={"status": ["open"]})
    assert duplicates.status_code == 200
    duplicate = next(row for row in duplicates.json() if row["batch_id"] == batch_id)

    ignored = client.post(
        f"/api/v1/imports/duplicates/{duplicate['id']}/ignore",
        headers=_headers(staff_csrf, nonce="ignore-duplicate-path"),
    )
    assert ignored.status_code == 200
    assert ignored.json()["status"] == "ignored"

    ignored_listing = client.get("/api/v1/imports/duplicates", params={"status": ["ignored"]})
    assert ignored_listing.status_code == 200
    assert any(row["id"] == duplicate["id"] and row["status"] == "ignored" for row in ignored_listing.json())
