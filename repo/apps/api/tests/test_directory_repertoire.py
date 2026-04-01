from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent
from app.db.session import get_engine


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _login(client, username: str, password: str):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response


def _switch_context(client, csrf_token: str, context: dict, nonce: str) -> None:
    response = client.post(
        "/api/v1/contexts/active",
        headers={
            "X-CSRF-Token": csrf_token,
            "X-Request-Nonce": nonce,
            "X-Request-Timestamp": _iso_now(),
        },
        json={
            "organization_id": context["organization_id"],
            "program_id": context["program_id"],
            "event_id": context["event_id"],
            "store_id": context["store_id"],
        },
    )
    assert response.status_code == 200


def test_directory_search_filters_and_active_context_scope(client):
    login = _login(client, "admin", "admin123!")
    csrf = login.json()["csrf_token"]

    actor_result = client.get("/api/v1/directory/search", params={"actor": "Ava"})
    assert actor_result.status_code == 200
    assert actor_result.json()["total"] == 1
    assert actor_result.json()["results"][0]["display_name"] == "Ava Martinez"

    tag_result = client.get("/api/v1/directory/search", params={"tags": ["drama"]})
    assert tag_result.status_code == 200
    assert {item["display_name"] for item in tag_result.json()["results"]} == {"Ben Carter"}

    repertoire_result = client.get("/api/v1/directory/search", params={"repertoire": "Moonlight"})
    assert repertoire_result.status_code == 200
    assert {item["display_name"] for item in repertoire_result.json()["results"]} == {"Ava Martinez", "Chloe Ng"}

    region_result = client.get("/api/v1/directory/search", params={"region": "North"})
    assert region_result.status_code == 200
    assert {item["display_name"] for item in region_result.json()["results"]} == {"Ava Martinez", "Chloe Ng"}

    contexts = client.get("/api/v1/contexts/available")
    assert contexts.status_code == 200
    choices = contexts.json()
    target = next(choice for choice in choices if choice["event_name"] == "Encore Matinee")
    _switch_context(client, csrf, target, nonce="9ca7f4f1-e483-4054-90b0-bec6f7a2d50a")

    scoped_result = client.get("/api/v1/directory/search", params={"actor": "Ava"})
    assert scoped_result.status_code == 200
    assert scoped_result.json()["total"] == 0


def test_directory_availability_overlap_filter(client):
    _login(client, "admin", "admin123!")

    response = client.get(
        "/api/v1/directory/search",
        params={
            "availability_start": "2026-04-01T18:30:00Z",
            "availability_end": "2026-04-01T19:00:00Z",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["results"][0]["display_name"] == "Ava Martinez"


def test_directory_fields_are_masked_by_default(client):
    _login(client, "student", "stud123!")

    response = client.get("/api/v1/directory/search", params={"actor": "Ava"})
    assert response.status_code == 200
    entry = response.json()["results"][0]
    assert entry["contact"]["masked"] is True
    assert entry["contact"]["email"] == "a***@harmonyhub.example"
    assert entry["contact"]["phone"] == "***-***-2233"
    assert entry["contact"]["address_line1"] == "*** Hidden address ***"

    detail = client.get(f"/api/v1/directory/{entry['id']}")
    assert detail.status_code == 200
    assert detail.json()["contact"]["masked"] is True


def test_directory_reveal_permission_is_enforced(client):
    student_login = _login(client, "student", "stud123!")
    student_csrf = student_login.json()["csrf_token"]
    entry_id = client.get("/api/v1/directory/search", params={"actor": "Ava"}).json()["results"][0]["id"]

    denied = client.post(
        f"/api/v1/directory/{entry_id}/reveal-contact",
        headers={
            "X-CSRF-Token": student_csrf,
            "X-Request-Nonce": "9f35f53f-e6f0-4414-8e93-979f95ff4284",
            "X-Request-Timestamp": _iso_now(),
        },
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN"

    staff_login = _login(client, "staff", "staff123!")
    staff_csrf = staff_login.json()["csrf_token"]
    allowed = client.post(
        f"/api/v1/directory/{entry_id}/reveal-contact",
        headers={
            "X-CSRF-Token": staff_csrf,
            "X-Request-Nonce": "18a2efca-bff2-4d52-bbb5-1b352f7be8b8",
            "X-Request-Timestamp": _iso_now(),
        },
    )
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["contact"]["masked"] is False
    assert payload["contact"]["email"] == "ava.martinez@harmonyhub.example"


def test_reveal_contact_persists_audit_event(client):
    staff_login = _login(client, "staff", "staff123!")
    staff_payload = staff_login.json()
    staff_csrf = staff_payload["csrf_token"]
    staff_id = client.get("/api/v1/auth/me").json()["user"]["id"]
    entry_id = client.get("/api/v1/directory/search", params={"actor": "Ava"}).json()["results"][0]["id"]

    reveal = client.post(
        f"/api/v1/directory/{entry_id}/reveal-contact",
        headers={
            "X-CSRF-Token": staff_csrf,
            "X-Request-Nonce": "2ab5d6e3-dd4d-4d8f-b745-90dcbf4dc599",
            "X-Request-Timestamp": _iso_now(),
        },
    )
    assert reveal.status_code == 200

    with Session(get_engine()) as session:
        audit_events = session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.action == "directory.contact.reveal",
                AuditEvent.target_type == "directory_entry",
                AuditEvent.target_id == entry_id,
            )
            .order_by(AuditEvent.created_at.desc())
        ).all()

    assert audit_events
    latest = audit_events[0]
    assert latest.actor_user_id == staff_id
    assert latest.actor_role == "staff"
    assert latest.details_json == {"revealed_fields": ["email", "phone", "address_line1"]}


def test_repertoire_search_filters_support_actor_tags_region_and_availability(client):
    _login(client, "admin", "admin123!")

    actor_result = client.get("/api/v1/repertoire/search", params={"actor": "Ava"})
    assert actor_result.status_code == 200
    assert {item["title"] for item in actor_result.json()["results"]} == {"Moonlight Sonata", "Summer Overture"}

    tag_result = client.get("/api/v1/repertoire/search", params={"tags": ["drama"]})
    assert tag_result.status_code == 200
    assert {item["title"] for item in tag_result.json()["results"]} == {"Shakespeare Nights"}

    region_result = client.get("/api/v1/repertoire/search", params={"region": "North"})
    assert region_result.status_code == 200
    assert {item["title"] for item in region_result.json()["results"]} == {"Moonlight Sonata", "Summer Overture"}

    availability_result = client.get(
        "/api/v1/repertoire/search",
        params={
            "availability_start": "2026-04-01T18:30:00Z",
            "availability_end": "2026-04-01T19:00:00Z",
        },
    )
    assert availability_result.status_code == 200
    assert {item["title"] for item in availability_result.json()["results"]} == {
        "Moonlight Sonata",
        "Summer Overture",
    }


def test_repertoire_detail_returns_performer_count_for_scoped_item(client):
    _login(client, "admin", "admin123!")
    search = client.get("/api/v1/repertoire/search", params={"repertoire": "Moonlight"})
    assert search.status_code == 200
    item_id = search.json()["results"][0]["id"]

    detail = client.get(f"/api/v1/repertoire/{item_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["title"] == "Moonlight Sonata"
    assert payload["performer_count"] >= 1
