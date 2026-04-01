from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DirectoryEntry
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


def _upsert_surface(client, csrf: str, surface: str, enabled: bool = True) -> None:
    response = client.put(
        f"/api/v1/admin/policies/abac/surfaces/{surface}",
        headers=_headers(csrf, nonce=f"surface-{surface}-{enabled}"),
        json={"enabled": enabled},
    )
    assert response.status_code == 200


def _create_rule(client, csrf: str, payload: dict, nonce: str) -> dict:
    response = client.post(
        "/api/v1/admin/policies/abac/rules",
        headers=_headers(csrf, nonce=nonce),
        json=payload,
    )
    assert response.status_code == 200
    return response.json()


def test_policy_simulation_supports_department_grade_class_dimensions(client):
    admin_csrf = _login(client, "admin", "admin123!")
    _upsert_surface(client, admin_csrf, "directory", True)

    deny_rule = _create_rule(
        client,
        admin_csrf,
        {
            "surface": "directory",
            "action": "contact_field_view",
            "effect": "deny",
            "priority": 10,
            "role": "staff",
            "subject_department": "operations",
            "subject_grade": "staff",
            "subject_class": "staff-a",
            "resource_department": "music",
            "resource_grade": "grade_10",
            "resource_class": "10A",
            "resource_field": "address_line1",
        },
        nonce="sim-dims-deny-rule",
    )
    allow_rule = _create_rule(
        client,
        admin_csrf,
        {
            "surface": "directory",
            "action": "contact_field_view",
            "effect": "allow",
            "priority": 20,
            "role": "staff",
            "subject_department": "operations",
            "subject_grade": "staff",
            "subject_class": "staff-a",
            "resource_department": "music",
            "resource_grade": "grade_10",
            "resource_class": "10A",
        },
        nonce="sim-dims-allow-rule",
    )

    denied = client.post(
        "/api/v1/admin/policies/simulate",
        json={
            "surface": "directory",
            "action": "contact_field_view",
            "role": "staff",
            "context": {},
            "subject": {
                "department": "operations",
                "grade": "staff",
                "class_code": "staff-a",
            },
            "resource": {
                "department": "music",
                "grade": "grade_10",
                "class_code": "10A",
                "field": "address_line1",
            },
        },
    )
    assert denied.status_code == 200
    denied_payload = denied.json()
    assert denied_payload["allowed"] is False
    assert denied_payload["matched_rule_id"] == deny_rule["id"]

    allowed = client.post(
        "/api/v1/admin/policies/simulate",
        json={
            "surface": "directory",
            "action": "contact_field_view",
            "role": "staff",
            "context": {},
            "subject": {
                "department": "operations",
                "grade": "staff",
                "class_code": "staff-a",
            },
            "resource": {
                "department": "music",
                "grade": "grade_10",
                "class_code": "10A",
                "field": "email",
            },
        },
    )
    assert allowed.status_code == 200
    allowed_payload = allowed.json()
    assert allowed_payload["allowed"] is True
    assert allowed_payload["matched_rule_id"] == allow_rule["id"]


def test_menu_visibility_supports_row_level_department_grade_class_scoping(client):
    admin_csrf = _login(client, "admin", "admin123!")
    _upsert_surface(client, admin_csrf, "ordering", True)

    _create_rule(
        client,
        admin_csrf,
        {
            "surface": "ordering",
            "action": "menu_items",
            "effect": "allow",
            "priority": 10,
            "role": "student",
            "subject_department": "music",
            "subject_grade": "grade_10",
            "subject_class": "10A",
        },
        nonce="ordering-menu-access",
    )
    _create_rule(
        client,
        admin_csrf,
        {
            "surface": "ordering",
            "action": "menu_row_view",
            "effect": "allow",
            "priority": 10,
            "role": "student",
            "subject_department": "music",
            "subject_grade": "grade_10",
            "subject_class": "10A",
            "resource_department": "music",
            "resource_grade": "grade_10",
        },
        nonce="ordering-menu-row",
    )

    _login(client, "student", "stud123!")
    menu = client.get("/api/v1/menu/items")
    assert menu.status_code == 200
    names = [item["name"] for item in menu.json()]
    assert names == ["Veggie Wrap"]


def test_directory_row_and_field_level_abac_enforcement_is_real(client):
    admin_csrf = _login(client, "admin", "admin123!")
    _upsert_surface(client, admin_csrf, "directory", True)

    with Session(get_engine()) as session:
        ava = session.scalar(select(DirectoryEntry).where(DirectoryEntry.display_name == "Ava Martinez"))
        ben = session.scalar(select(DirectoryEntry).where(DirectoryEntry.display_name == "Ben Carter"))
        chloe = session.scalar(select(DirectoryEntry).where(DirectoryEntry.display_name == "Chloe Ng"))
        assert ava is not None and ben is not None and chloe is not None

        ava.department = "music"
        ava.grade_level = "grade_10"
        ava.class_code = "10A"

        ben.department = "athletics"
        ben.grade_level = "grade_11"
        ben.class_code = "11R"

        chloe.department = "music"
        chloe.grade_level = "grade_10"
        chloe.class_code = "10B"

        ava_id = ava.id
        session.add_all([ava, ben, chloe])
        session.commit()

    _create_rule(
        client,
        admin_csrf,
        {
            "surface": "directory",
            "action": "search",
            "effect": "allow",
            "priority": 10,
            "role": "student",
            "subject_department": "music",
            "subject_grade": "grade_10",
            "subject_class": "10A",
        },
        nonce="dir-search-access",
    )
    _create_rule(
        client,
        admin_csrf,
        {
            "surface": "directory",
            "action": "search_row",
            "effect": "allow",
            "priority": 10,
            "role": "student",
            "subject_department": "music",
            "subject_grade": "grade_10",
            "subject_class": "10A",
            "resource_department": "music",
            "resource_grade": "grade_10",
            "resource_class": "10A",
        },
        nonce="dir-search-row",
    )

    _login(client, "student", "stud123!")
    search = client.get("/api/v1/directory/search")
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    assert payload["results"][0]["display_name"] == "Ava Martinez"

    admin_csrf = _login(client, "admin", "admin123!")

    _create_rule(
        client,
        admin_csrf,
        {
            "surface": "directory",
            "action": "reveal_contact",
            "effect": "allow",
            "priority": 10,
            "role": "staff",
            "subject_department": "operations",
            "subject_grade": "staff",
            "subject_class": "staff-a",
        },
        nonce="dir-reveal-access",
    )
    _create_rule(
        client,
        admin_csrf,
        {
            "surface": "directory",
            "action": "reveal_row",
            "effect": "allow",
            "priority": 10,
            "role": "staff",
            "subject_department": "operations",
            "subject_grade": "staff",
            "subject_class": "staff-a",
            "resource_department": "music",
            "resource_grade": "grade_10",
            "resource_class": "10A",
        },
        nonce="dir-reveal-row",
    )
    _create_rule(
        client,
        admin_csrf,
        {
            "surface": "directory",
            "action": "contact_field_view",
            "effect": "allow",
            "priority": 10,
            "role": "staff",
            "subject_department": "operations",
            "subject_grade": "staff",
            "subject_class": "staff-a",
            "resource_department": "music",
            "resource_grade": "grade_10",
            "resource_class": "10A",
            "resource_field": "email",
        },
        nonce="dir-field-email",
    )
    _create_rule(
        client,
        admin_csrf,
        {
            "surface": "directory",
            "action": "contact_field_view",
            "effect": "allow",
            "priority": 11,
            "role": "staff",
            "subject_department": "operations",
            "subject_grade": "staff",
            "subject_class": "staff-a",
            "resource_department": "music",
            "resource_grade": "grade_10",
            "resource_class": "10A",
            "resource_field": "phone",
        },
        nonce="dir-field-phone",
    )

    staff_csrf = _login(client, "staff", "staff123!")

    reveal = client.post(
        f"/api/v1/directory/{ava_id}/reveal-contact",
        headers=_headers(staff_csrf, nonce="dir-reveal-contact"),
    )
    assert reveal.status_code == 200
    contact = reveal.json()["contact"]
    assert contact["email"] is not None
    assert contact["phone"] is not None
    assert contact["address_line1"] is None
