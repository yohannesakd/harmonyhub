from __future__ import annotations

import uuid


def test_live_health(client):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_health(client):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_successful_responses_carry_x_request_id(client):
    """Every response passes through request_context_middleware which stamps
    X-Request-ID.  Assert the header is present and parses as a valid UUID so
    that middleware observability is covered by at least one explicit assertion."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    request_id = response.headers.get("x-request-id", "")
    assert request_id, "X-Request-ID header must be present on successful responses"
    # Must be a well-formed UUID (not just any non-empty string)
    uuid.UUID(request_id)  # raises ValueError if malformed
