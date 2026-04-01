from __future__ import annotations

from datetime import UTC, datetime


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _login(client, username: str, password: str, totp_code: str | None = None):
    payload: dict[str, str] = {"username": username, "password": password}
    if totp_code:
        payload["totp_code"] = totp_code
    return client.post("/api/v1/auth/login", json=payload)


def test_login_and_me_reflect_active_context_and_permissions(client):
    login = _login(client, "admin", "admin123!")
    assert login.status_code == 200

    login_payload = login.json()
    assert login_payload["active_context"] is not None
    assert "dashboard.view" in login_payload["permissions"]

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["user"]["username"] == "admin"
    assert len(me_payload["available_contexts"]) >= 3
    assert me_payload["active_context"]["event_id"]


def test_context_switch_changes_dashboard_context(client):
    login = _login(client, "admin", "admin123!")
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]

    contexts = client.get("/api/v1/contexts/available")
    assert contexts.status_code == 200
    choices = contexts.json()
    assert len(choices) >= 2

    before = client.get("/api/v1/dashboard/event")
    assert before.status_code == 200
    before_event = before.json()["event_name"]

    target = next((choice for choice in choices if choice["event_name"] != before_event), choices[0])
    switched = client.post(
        "/api/v1/contexts/active",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "5c98b83b-d57e-4afe-a6f6-041afdf1f314",
            "X-Request-Timestamp": _iso_now(),
        },
        json={
            "organization_id": target["organization_id"],
            "program_id": target["program_id"],
            "event_id": target["event_id"],
            "store_id": target["store_id"],
        },
    )
    assert switched.status_code == 200
    assert switched.json()["active_context"]["event_id"] == target["event_id"]

    after = client.get("/api/v1/dashboard/event")
    assert after.status_code == 200
    after_event = after.json()["event_name"]
    assert after_event != before_event


def test_logout_clears_session_and_blocks_follow_up_me_requests(client):
    login = _login(client, "admin", "admin123!")
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]

    logout = client.post(
        "/api/v1/auth/logout",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "logout-nonce",
            "X-Request-Timestamp": _iso_now(),
        },
    )
    assert logout.status_code == 200
    assert logout.json()["status"] == "logged_out"

    me_after_logout = client.get("/api/v1/auth/me")
    assert me_after_logout.status_code == 401
    assert me_after_logout.json()["error"]["code"] == "AUTH_REQUIRED"
