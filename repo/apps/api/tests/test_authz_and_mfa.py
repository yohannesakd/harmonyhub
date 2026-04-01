from __future__ import annotations

from datetime import UTC, datetime

import pyotp


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _login(client, username: str, password: str, totp_code: str | None = None):
    payload: dict[str, str] = {"username": username, "password": password}
    if totp_code:
        payload["totp_code"] = totp_code
    return client.post("/api/v1/auth/login", json=payload)


def test_default_deny_student_cannot_manage_abac_policies(client):
    login = _login(client, "student", "stud123!")
    assert login.status_code == 200

    forbidden = client.get("/api/v1/admin/policies/abac/surfaces")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"


def test_totp_mfa_enablement_and_required_on_login(client):
    login = _login(client, "staff", "staff123!")
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]

    setup = client.post(
        "/api/v1/auth/mfa/totp/setup",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "965ca275-3f4f-46f0-837e-0900e8f9867c",
            "X-Request-Timestamp": _iso_now(),
        },
    )
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()

    verify = client.post(
        "/api/v1/auth/mfa/totp/verify",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "6a2d4c84-0dd3-4c75-baf2-a1d7303054ca",
            "X-Request-Timestamp": _iso_now(),
        },
        json={"code": code},
    )
    assert verify.status_code == 200
    assert verify.json()["valid"] is True

    enable = client.post(
        "/api/v1/auth/mfa/totp/enable",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "e092f078-31f4-4f66-8942-81f9464edace",
            "X-Request-Timestamp": _iso_now(),
        },
        json={"code": code},
    )
    assert enable.status_code == 200
    assert enable.json()["mfa_totp_enabled"] is True

    # Login without TOTP should now fail.
    mfa_required = _login(client, "staff", "staff123!")
    assert mfa_required.status_code == 401
    assert mfa_required.json()["error"]["code"] == "MFA_REQUIRED"

    login_with_totp = _login(client, "staff", "staff123!", pyotp.TOTP(secret).now())
    assert login_with_totp.status_code == 200


def test_abac_surface_enablement_can_deny_dashboard_access(client):
    admin_login = _login(client, "admin", "admin123!")
    assert admin_login.status_code == 200
    csrf = admin_login.json()["csrf_token"]

    enable_surface = client.put(
        "/api/v1/admin/policies/abac/surfaces/dashboard",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "5d42b755-8e5d-44b7-9c23-8f170d1545bf",
            "X-Request-Timestamp": _iso_now(),
        },
        json={"enabled": True},
    )
    assert enable_surface.status_code == 200

    create_rule = client.post(
        "/api/v1/admin/policies/abac/rules",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "1f3de3a8-43ce-47d9-a128-859d89fd2e11",
            "X-Request-Timestamp": _iso_now(),
        },
        json={
            "surface": "dashboard",
            "action": "view",
            "effect": "deny",
            "priority": 10,
            "role": "referee",
        },
    )
    assert create_rule.status_code == 200

    ref_login = _login(client, "referee", "ref123!")
    assert ref_login.status_code == 200

    denied_dashboard = client.get("/api/v1/dashboard/event")
    assert denied_dashboard.status_code == 403
    assert denied_dashboard.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_list_and_delete_abac_rules(client):
    admin_login = _login(client, "admin", "admin123!")
    assert admin_login.status_code == 200
    csrf = admin_login.json()["csrf_token"]

    created = client.post(
        "/api/v1/admin/policies/abac/rules",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "create-delete-rule",
            "X-Request-Timestamp": _iso_now(),
        },
        json={
            "surface": "dashboard",
            "action": "view",
            "effect": "deny",
            "priority": 5,
            "role": "student",
        },
    )
    assert created.status_code == 200
    rule_id = created.json()["id"]

    listed = client.get("/api/v1/admin/policies/abac/rules", params={"surface": "dashboard", "action": "view"})
    assert listed.status_code == 200
    assert any(rule["id"] == rule_id for rule in listed.json())

    deleted = client.delete(
        f"/api/v1/admin/policies/abac/rules/{rule_id}",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "delete-created-rule",
            "X-Request-Timestamp": _iso_now(),
        },
    )
    assert deleted.status_code == 200

    listed_after = client.get("/api/v1/admin/policies/abac/rules", params={"surface": "dashboard", "action": "view"})
    assert listed_after.status_code == 200
    assert all(rule["id"] != rule_id for rule in listed_after.json())
