from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.core.security import decode_session_token


def _iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _login(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123!"},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _first_context(client):
    contexts_response = client.get("/api/v1/contexts/available")
    assert contexts_response.status_code == 200
    payload = contexts_response.json()
    assert payload
    return payload[0]


def test_rejects_stale_replay_timestamp(client):
    csrf = _login(client)
    context = _first_context(client)

    stale_ts = _iso(datetime.now(UTC) - timedelta(minutes=10))
    response = client.post(
        "/api/v1/contexts/active",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "5f8f3a24-f412-4112-b4a9-07f21891ca0a",
            "X-Request-Timestamp": stale_ts,
        },
        json={
            "organization_id": context["organization_id"],
            "program_id": context["program_id"],
            "event_id": context["event_id"],
            "store_id": context["store_id"],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REPLAY_REJECTED"


def test_rejects_reused_nonce_within_window(client):
    csrf = _login(client)
    context = _first_context(client)

    nonce = "2ec57f78-c53d-4b27-855a-2a1d9bf52997"
    ts = _iso(datetime.now(UTC))

    first = client.post(
        "/api/v1/contexts/active",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": nonce,
            "X-Request-Timestamp": ts,
        },
        json={
            "organization_id": context["organization_id"],
            "program_id": context["program_id"],
            "event_id": context["event_id"],
            "store_id": context["store_id"],
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/contexts/active",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": nonce,
            "X-Request-Timestamp": ts,
        },
        json={
            "organization_id": context["organization_id"],
            "program_id": context["program_id"],
            "event_id": context["event_id"],
            "store_id": context["store_id"],
        },
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "REPLAY_REJECTED"


def test_rejects_csrf_mismatch_on_mutation(client):
    _login(client)
    ts = _iso(datetime.now(UTC))

    response = client.post(
        "/api/v1/auth/logout",
        headers={
            "X-CSRF-Token": "csrf-token-that-does-not-match-cookie",
            "X-Request-Nonce": "c2530f78-7781-4b97-b7e4-6e2d450f540a",
            "X-Request-Timestamp": ts,
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_INVALID"


def test_locks_account_after_repeated_failed_login_attempts(client):
    for _ in range(5):
        failed = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )
        assert failed.status_code == 401

    locked = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123!"},
    )
    assert locked.status_code == 423
    assert locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert "locked_until" in locked.json()["error"]["details"]


def test_decode_session_token_tolerates_small_clock_skew():
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "user-1",
            "username": "tester",
            "ctx": {},
            "iat": int((now + timedelta(seconds=2)).timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    decoded = decode_session_token(token)
    assert decoded["sub"] == "user-1"
