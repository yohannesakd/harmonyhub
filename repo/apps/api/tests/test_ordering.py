from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _aligned_slot(minutes_ahead: int = 120) -> str:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    floored = now.replace(minute=(now.minute // 15) * 15)
    slot = floored + timedelta(minutes=minutes_ahead)
    return slot.isoformat().replace("+00:00", "Z")


def _login(client, username: str, password: str):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response


def _headers(csrf: str, nonce: str):
    return {
        "X-CSRF-Token": csrf,
        "X-Request-Nonce": nonce,
        "X-Request-Timestamp": _iso_now(),
    }


def _first_menu_item_id(client) -> str:
    menu = client.get("/api/v1/menu/items")
    assert menu.status_code == 200
    items = menu.json()
    assert items
    return items[0]["id"]


def _create_address(client, csrf: str, zip_code: str = "10001") -> str:
    created = client.post(
        "/api/v1/addresses",
        headers=_headers(csrf, nonce=f"addr-{zip_code}-{datetime.now(UTC).timestamp()}"),
        json={
            "label": "Home",
            "recipient_name": "Student User",
            "line1": "123 Main Street",
            "line2": None,
            "city": "New York",
            "state": "ny",
            "postal_code": zip_code,
            "phone": "555-111-0000",
            "is_default": True,
        },
    )
    assert created.status_code == 200
    return created.json()["id"]


def _create_draft(client, csrf: str, *, order_type: str, menu_item_id: str, slot_start: str, address_id: str | None = None) -> str:
    payload = {
        "order_type": order_type,
        "slot_start": slot_start,
        "address_book_entry_id": address_id,
        "lines": [{"menu_item_id": menu_item_id, "quantity": 1}],
    }
    response = client.post(
        "/api/v1/orders/drafts",
        headers=_headers(csrf, nonce=f"draft-{datetime.now(UTC).timestamp()}"),
        json=payload,
    )
    assert response.status_code == 200
    return response.json()["id"]


def _quote_order(client, csrf: str, order_id: str, nonce: str):
    return client.post(f"/api/v1/orders/{order_id}/quote", headers=_headers(csrf, nonce=nonce))


def _confirm_order(client, csrf: str, order_id: str, nonce: str):
    return client.post(f"/api/v1/orders/{order_id}/confirm", headers=_headers(csrf, nonce=nonce))


def test_address_book_crud_and_ownership_scope(client):
    student_login = _login(client, "student", "stud123!")
    student_csrf = student_login.json()["csrf_token"]
    address_id = _create_address(client, student_csrf, zip_code="10001")

    listed = client.get("/api/v1/addresses")
    assert listed.status_code == 200
    assert {row["id"] for row in listed.json()} == {address_id}

    updated = client.put(
        f"/api/v1/addresses/{address_id}",
        headers=_headers(student_csrf, nonce="addr-update-student"),
        json={
            "label": "Home Updated",
            "recipient_name": "Student User",
            "line1": "500 Park Ave",
            "line2": "Apt 3",
            "city": "New York",
            "state": "NY",
            "postal_code": "10001",
            "phone": "555-111-0001",
            "is_default": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Home Updated"

    staff_login = _login(client, "staff", "staff123!")
    staff_csrf = staff_login.json()["csrf_token"]

    forbidden_update = client.put(
        f"/api/v1/addresses/{address_id}",
        headers=_headers(staff_csrf, nonce="addr-update-staff"),
        json={
            "label": "Nope",
            "recipient_name": "Staff User",
            "line1": "1 Staff St",
            "line2": None,
            "city": "New York",
            "state": "NY",
            "postal_code": "10001",
            "phone": None,
            "is_default": False,
        },
    )
    assert forbidden_update.status_code == 404

    forbidden_delete = client.delete(
        f"/api/v1/addresses/{address_id}",
        headers=_headers(staff_csrf, nonce="addr-delete-staff"),
    )
    assert forbidden_delete.status_code == 404

    # Re-auth as student because single TestClient keeps one active session cookie jar.
    student_login = _login(client, "student", "stud123!")
    student_csrf = student_login.json()["csrf_token"]

    deleted = client.delete(
        f"/api/v1/addresses/{address_id}",
        headers=_headers(student_csrf, nonce="addr-delete-student"),
    )
    assert deleted.status_code == 200


def test_delivery_zip_zone_fee_matching_and_pickup_zero_fee(client):
    login = _login(client, "student", "stud123!")
    csrf = login.json()["csrf_token"]
    menu_item_id = _first_menu_item_id(client)
    slot_start = _aligned_slot(120)

    address_id = _create_address(client, csrf, zip_code="10001")
    delivery_order_id = _create_draft(
        client,
        csrf,
        order_type="delivery",
        menu_item_id=menu_item_id,
        slot_start=slot_start,
        address_id=address_id,
    )

    quoted_delivery = _quote_order(client, csrf, delivery_order_id, nonce="quote-delivery-fee")
    assert quoted_delivery.status_code == 200
    assert quoted_delivery.json()["delivery_fee_cents"] == 350

    pickup_order_id = _create_draft(
        client,
        csrf,
        order_type="pickup",
        menu_item_id=menu_item_id,
        slot_start=slot_start,
    )
    quoted_pickup = _quote_order(client, csrf, pickup_order_id, nonce="quote-pickup-fee")
    assert quoted_pickup.status_code == 200
    assert quoted_pickup.json()["delivery_fee_cents"] == 0


def test_delivery_order_fails_when_zip_has_no_active_zone(client):
    login = _login(client, "student", "stud123!")
    csrf = login.json()["csrf_token"]
    menu_item_id = _first_menu_item_id(client)
    slot_start = _aligned_slot(150)

    out_of_zone_address_id = _create_address(client, csrf, zip_code="99999")
    payload = {
        "order_type": "delivery",
        "slot_start": slot_start,
        "address_book_entry_id": out_of_zone_address_id,
        "lines": [{"menu_item_id": menu_item_id, "quantity": 1}],
    }
    drafted = client.post(
        "/api/v1/orders/drafts",
        headers=_headers(csrf, nonce=f"draft-out-of-zone-{datetime.now(UTC).timestamp()}"),
        json=payload,
    )
    assert drafted.status_code == 422
    error = drafted.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert "outside active delivery zones" in error["message"]
    assert error["details"]["zip_code"] == "99999"


def test_scheduling_endpoints_require_scheduling_manage_permission(client):
    login = _login(client, "student", "stud123!")
    csrf = login.json()["csrf_token"]
    slot_start = _aligned_slot(60)

    list_zones = client.get("/api/v1/scheduling/delivery-zones")
    assert list_zones.status_code == 403

    upsert_capacity = client.put(
        "/api/v1/scheduling/slot-capacities",
        headers=_headers(csrf, nonce="student-capacity-attempt"),
        json={"slot_start": slot_start, "capacity": 1},
    )
    assert upsert_capacity.status_code == 403


def test_capacity_enforced_on_finalize_with_next_slot_suggestions(client):
    staff_login = _login(client, "staff", "staff123!")
    staff_csrf = staff_login.json()["csrf_token"]
    slot_start = _aligned_slot(45)

    set_capacity = client.put(
        "/api/v1/scheduling/slot-capacities",
        headers=_headers(staff_csrf, nonce="cap-set-1"),
        json={"slot_start": slot_start, "capacity": 1},
    )
    assert set_capacity.status_code == 200

    student_login = _login(client, "student", "stud123!")
    student_csrf = student_login.json()["csrf_token"]
    menu_item_id = _first_menu_item_id(client)

    first_order_id = _create_draft(
        client,
        student_csrf,
        order_type="pickup",
        menu_item_id=menu_item_id,
        slot_start=slot_start,
    )
    assert _quote_order(client, student_csrf, first_order_id, nonce="quote-first").status_code == 200

    referee_login = _login(client, "referee", "ref123!")
    referee_csrf = referee_login.json()["csrf_token"]
    second_order_id = _create_draft(
        client,
        referee_csrf,
        order_type="pickup",
        menu_item_id=menu_item_id,
        slot_start=slot_start,
    )
    assert _quote_order(client, referee_csrf, second_order_id, nonce="quote-second").status_code == 200

    student_login = _login(client, "student", "stud123!")
    student_csrf = student_login.json()["csrf_token"]
    first_confirm = _confirm_order(client, student_csrf, first_order_id, nonce="confirm-first")
    assert first_confirm.status_code == 200
    assert first_confirm.json()["status"] == "confirmed"

    referee_login = _login(client, "referee", "ref123!")
    referee_csrf = referee_login.json()["csrf_token"]

    second_confirm = _confirm_order(client, referee_csrf, second_order_id, nonce="confirm-second")
    assert second_confirm.status_code == 409
    payload = second_confirm.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["details"]["next_slots"]

    expected_next = (
        datetime.fromisoformat(slot_start.replace("Z", "+00:00")) + timedelta(minutes=15)
    ).isoformat()
    assert payload["details"]["next_slots"][0].startswith(expected_next[:16])


def test_eta_recalculates_from_confirmed_queue_depth(client):
    staff_login = _login(client, "staff", "staff123!")
    staff_csrf = staff_login.json()["csrf_token"]
    slot_start = _aligned_slot(0)
    set_capacity = client.put(
        "/api/v1/scheduling/slot-capacities",
        headers=_headers(staff_csrf, nonce="eta-capacity-set"),
        json={"slot_start": slot_start, "capacity": 10},
    )
    assert set_capacity.status_code == 200

    student_login = _login(client, "student", "stud123!")
    student_csrf = student_login.json()["csrf_token"]
    menu_item_id = _first_menu_item_id(client)

    baseline_order_id = _create_draft(
        client,
        student_csrf,
        order_type="pickup",
        menu_item_id=menu_item_id,
        slot_start=slot_start,
    )
    baseline_quote = _quote_order(client, student_csrf, baseline_order_id, nonce="eta-baseline")
    assert baseline_quote.status_code == 200
    baseline_eta = baseline_quote.json()["eta_minutes"]
    assert baseline_eta is not None

    first_confirm_order = _create_draft(
        client,
        student_csrf,
        order_type="pickup",
        menu_item_id=menu_item_id,
        slot_start=slot_start,
    )
    assert _quote_order(client, student_csrf, first_confirm_order, nonce="eta-q1").status_code == 200
    assert _confirm_order(client, student_csrf, first_confirm_order, nonce="eta-c1").status_code == 200

    referee_login = _login(client, "referee", "ref123!")
    referee_csrf = referee_login.json()["csrf_token"]
    second_confirm_order = _create_draft(
        client,
        referee_csrf,
        order_type="pickup",
        menu_item_id=menu_item_id,
        slot_start=slot_start,
    )
    assert _quote_order(client, referee_csrf, second_confirm_order, nonce="eta-q2").status_code == 200
    assert _confirm_order(client, referee_csrf, second_confirm_order, nonce="eta-c2").status_code == 200

    student_login = _login(client, "student", "stud123!")
    student_csrf = student_login.json()["csrf_token"]
    requoted = _quote_order(client, student_csrf, baseline_order_id, nonce="eta-requote")
    assert requoted.status_code == 200
    assert requoted.json()["eta_minutes"] > baseline_eta


def test_order_update_list_and_cancel_flow(client):
    login = _login(client, "student", "stud123!")
    csrf = login.json()["csrf_token"]
    menu_item_id = _first_menu_item_id(client)
    slot_start = _aligned_slot(135)

    draft_id = _create_draft(
        client,
        csrf,
        order_type="pickup",
        menu_item_id=menu_item_id,
        slot_start=slot_start,
    )

    updated = client.put(
        f"/api/v1/orders/{draft_id}/draft",
        headers=_headers(csrf, nonce="update-draft-for-cancel"),
        json={
            "order_type": "pickup",
            "slot_start": slot_start,
            "address_book_entry_id": None,
            "lines": [{"menu_item_id": menu_item_id, "quantity": 2}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "draft"
    assert updated.json()["lines"][0]["quantity"] == 2

    listed = client.get("/api/v1/orders/mine")
    assert listed.status_code == 200
    assert draft_id in {row["id"] for row in listed.json()}

    quoted = _quote_order(client, csrf, draft_id, nonce="cancel-flow-quote")
    assert quoted.status_code == 200
    confirmed = _confirm_order(client, csrf, draft_id, nonce="cancel-flow-confirm")
    assert confirmed.status_code == 200

    cancelled = client.post(
        f"/api/v1/orders/{draft_id}/cancel",
        headers=_headers(csrf, nonce="cancel-flow-first"),
        json={"reason": "schedule changed"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancel_reason"] == "schedule changed"

    cancelled_again = client.post(
        f"/api/v1/orders/{draft_id}/cancel",
        headers=_headers(csrf, nonce="cancel-flow-second"),
        json={"reason": "idempotent"},
    )
    assert cancelled_again.status_code == 200
    assert cancelled_again.json()["status"] == "cancelled"


def test_scheduling_staff_crud_for_delivery_zone_and_slot_capacity(client):
    login = _login(client, "staff", "staff123!")
    csrf = login.json()["csrf_token"]

    created_zone = client.post(
        "/api/v1/scheduling/delivery-zones",
        headers=_headers(csrf, nonce="create-delivery-zone"),
        json={"zip_code": "30301", "flat_fee_cents": 450, "is_active": True},
    )
    assert created_zone.status_code == 200
    zone_id = created_zone.json()["id"]

    updated_zone = client.put(
        f"/api/v1/scheduling/delivery-zones/{zone_id}",
        headers=_headers(csrf, nonce="update-delivery-zone"),
        json={"zip_code": "30301", "flat_fee_cents": 500, "is_active": True},
    )
    assert updated_zone.status_code == 200
    assert updated_zone.json()["flat_fee_cents"] == 500

    deleted_zone = client.delete(
        f"/api/v1/scheduling/delivery-zones/{zone_id}",
        headers=_headers(csrf, nonce="delete-delivery-zone"),
    )
    assert deleted_zone.status_code == 200

    slot_start = _aligned_slot(180)
    upsert_slot = client.put(
        "/api/v1/scheduling/slot-capacities",
        headers=_headers(csrf, nonce="create-slot-capacity"),
        json={"slot_start": slot_start, "capacity": 3},
    )
    assert upsert_slot.status_code == 200
    assert upsert_slot.json()["capacity"] == 3

    slot_date = datetime.fromisoformat(slot_start.replace("Z", "+00:00")).date().isoformat()
    listed_slots = client.get("/api/v1/scheduling/slot-capacities", params={"for_date": slot_date})
    assert listed_slots.status_code == 200
    assert any(row["slot_start"].startswith(slot_date) for row in listed_slots.json())

    deleted_slot = client.delete(
        "/api/v1/scheduling/slot-capacities",
        headers=_headers(csrf, nonce="delete-slot-capacity"),
        params={"slot_start": slot_start},
    )
    assert deleted_slot.status_code == 200
