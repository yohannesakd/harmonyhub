from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.imports.sensitive_json import ENCRYPTED_IMPORT_JSON_KEY
from app.db.models import AddressBookEntry, UploadedAsset, User
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


def test_sensitive_strings_are_ciphertext_at_rest_but_readable_via_orm(client):
    staff_csrf = _login(client, "staff", "staff123!")
    setup = client.post(
        "/api/v1/auth/mfa/totp/setup",
        headers=_headers(staff_csrf, "totp-setup-encryption-test"),
    )
    assert setup.status_code == 200
    plain_secret = setup.json()["secret"]

    student_csrf = _login(client, "student", "stud123!")
    created = client.post(
        "/api/v1/addresses",
        headers=_headers(student_csrf, "address-create-encryption-test"),
        json={
            "label": "Home",
            "recipient_name": "Student User",
            "line1": "123 Main Street",
            "line2": "Apartment 2",
            "city": "New York",
            "state": "NY",
            "postal_code": "10001",
            "phone": "555-111-0000",
            "is_default": True,
        },
    )
    assert created.status_code == 200

    with Session(get_engine()) as session:
        row = session.execute(text("SELECT mfa_totp_secret FROM users WHERE username = 'staff' LIMIT 1")).first()
        assert row is not None
        encrypted_secret = row[0]
        assert isinstance(encrypted_secret, str)
        assert encrypted_secret.startswith("enc::")
        assert encrypted_secret != plain_secret

        address_row = session.execute(
            text(
                "SELECT recipient_name, line1, line2, phone "
                "FROM address_book_entries "
                "WHERE label = 'Home' "
                "ORDER BY created_at DESC LIMIT 1"
            )
        ).first()
        assert address_row is not None
        for value in address_row:
            if value is None:
                continue
            assert isinstance(value, str)
            assert value.startswith("enc::")

        orm_user = session.scalar(select(User).where(User.username == "staff"))
        assert orm_user is not None
        assert orm_user.mfa_totp_secret == plain_secret

        orm_address = session.scalar(
            select(AddressBookEntry).where(AddressBookEntry.label == "Home").order_by(AddressBookEntry.created_at.desc()).limit(1)
        )
        assert orm_address is not None
        assert orm_address.recipient_name == "Student User"
        assert orm_address.line1 == "123 Main Street"
        assert orm_address.line2 == "Apartment 2"
        assert orm_address.phone == "555-111-0000"


def test_uploaded_asset_bytes_are_ciphertext_at_rest_and_import_pipeline_still_reads_them(client):
    staff_csrf = _login(client, "staff", "staff123!")
    raw_csv = b"display_name,email,region\nCipher Upload,cipher@example.com,North Region\n"

    uploaded = client.post(
        "/api/v1/imports/batches/upload",
        data={"kind": "member"},
        files={"file": ("members.csv", raw_csv, "text/csv")},
        headers=_headers(staff_csrf, "upload-encryption-test"),
    )
    assert uploaded.status_code == 200
    batch_id = uploaded.json()["batch"]["id"]
    upload_id = uploaded.json()["upload"]["id"]

    with Session(get_engine()) as session:
        db_row = session.execute(text("SELECT raw_bytes FROM uploaded_assets WHERE id = :id"), {"id": upload_id}).first()
        assert db_row is not None
        encrypted_blob = db_row[0]
        if isinstance(encrypted_blob, memoryview):
            encrypted_blob = encrypted_blob.tobytes()
        assert isinstance(encrypted_blob, bytes)
        assert encrypted_blob.startswith(b"enc::")
        assert encrypted_blob != raw_csv

        orm_asset = session.scalar(select(UploadedAsset).where(UploadedAsset.id == upload_id))
        assert orm_asset is not None
        assert orm_asset.raw_bytes == raw_csv

    normalized = client.post(
        f"/api/v1/imports/batches/{batch_id}/normalize",
        headers=_headers(staff_csrf, "normalize-encryption-test"),
    )
    assert normalized.status_code == 200

    with Session(get_engine()) as session:
        raw_row = session.execute(
            text(
                "SELECT raw_row_json, normalized_json "
                "FROM import_normalized_rows "
                "WHERE batch_id = :batch_id "
                "ORDER BY row_number ASC LIMIT 1"
            ),
            {"batch_id": batch_id},
        ).first()
        assert raw_row is not None
        stored_raw = raw_row[0]
        stored_normalized = raw_row[1]

        def _to_dict(value):
            if isinstance(value, str):
                return json.loads(value)
            return value

        raw_json = _to_dict(stored_raw)
        normalized_json = _to_dict(stored_normalized)
        assert isinstance(raw_json, dict)
        assert isinstance(normalized_json, dict)
        assert ENCRYPTED_IMPORT_JSON_KEY in raw_json
        assert ENCRYPTED_IMPORT_JSON_KEY in normalized_json
        assert "Cipher Upload" not in json.dumps(raw_json)
        assert "cipher@example.com" not in json.dumps(normalized_json)

    detail = client.get(f"/api/v1/imports/batches/{batch_id}")
    assert detail.status_code == 200
    first_row = detail.json()["rows"][0]
    assert first_row["raw_row_json"]["display_name"] == "Cipher Upload"
    assert first_row["normalized_json"]["display_name"] == "Cipher Upload"
