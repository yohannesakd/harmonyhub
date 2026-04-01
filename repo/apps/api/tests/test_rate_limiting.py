from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def freeze_rate_limit_clock(monkeypatch):
    from app import main as app_main

    fixed_now = datetime(2026, 1, 1, 12, 0, 30, tzinfo=UTC)
    monkeypatch.setattr(app_main, "current_utc_time", lambda: fixed_now)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_rate_limit_enforces_60_per_minute_for_authenticated_user(client):
    _login(client, "staff", "staff123!")

    for _ in range(60):
        response = client.get("/api/v1/dashboard/event")
        assert response.status_code == 200
        assert response.headers.get("X-RateLimit-User-Limit") == "60"

    blocked = client.get("/api/v1/dashboard/event")
    assert blocked.status_code == 429
    payload = blocked.json()
    assert payload["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert payload["error"]["details"]["scope"] == "user"
    assert payload["error"]["details"]["limit"] == 60
    assert blocked.headers.get("X-RateLimit-Scope") == "user"
    assert blocked.headers.get("Retry-After") is not None


def test_rate_limit_enforces_300_per_minute_per_ip_on_auth_entrypoint():
    with TestClient(create_app(), client=("203.0.113.10", 50000)) as ip_one_client:
        for index in range(300):
            response = ip_one_client.post(
                "/api/v1/auth/login",
                json={"username": f"ghost-{index}", "password": "invalid"},
            )
            assert response.status_code == 401

        blocked = ip_one_client.post(
            "/api/v1/auth/login",
            json={"username": "ghost-blocked", "password": "invalid"},
        )
        assert blocked.status_code == 429
        payload = blocked.json()
        assert payload["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert payload["error"]["details"]["scope"] == "ip"
        assert payload["error"]["details"]["limit"] == 300
        assert blocked.headers.get("X-RateLimit-Scope") == "ip"
        assert blocked.headers.get("Retry-After") is not None

    with TestClient(create_app(), client=("203.0.113.11", 50001)) as ip_two_client:
        different_ip = ip_two_client.post(
            "/api/v1/auth/login",
            json={"username": "ghost-other-ip", "password": "invalid"},
        )
        assert different_ip.status_code == 401


def test_rate_limit_uses_last_untrusted_ip_in_forwarded_chain(monkeypatch):
    monkeypatch.setenv("HH_TRUSTED_PROXY_CIDRS", "172.16.0.0/12")
    get_settings.cache_clear()

    with TestClient(create_app(), client=("172.20.0.2", 50002)) as proxy_client:
        for index in range(300):
            spoofed_first_hop = f"198.51.100.{(index % 200) + 1}"
            response = proxy_client.post(
                "/api/v1/auth/login",
                headers={"X-Forwarded-For": f"{spoofed_first_hop}, 203.0.113.10"},
                json={"username": f"ghost-proxy-{index}", "password": "invalid"},
            )
            assert response.status_code == 401

        blocked = proxy_client.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": "198.51.100.250, 203.0.113.10"},
            json={"username": "ghost-proxy-blocked", "password": "invalid"},
        )
        assert blocked.status_code == 429
        payload = blocked.json()
        assert payload["error"]["details"]["scope"] == "ip"

        fresh_client_ip = proxy_client.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": "198.51.100.250, 203.0.113.11"},
            json={"username": "ghost-proxy-fresh", "password": "invalid"},
        )
        assert fresh_client_ip.status_code == 401
