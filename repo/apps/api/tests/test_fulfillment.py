from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Order
from app.db.session import get_engine


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _aligned_slot(minutes_ahead: int = 90) -> str:
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    floored = now.replace(minute=(now.minute // 15) * 15)
    return (floored + timedelta(minutes=minutes_ahead)).isoformat().replace("+00:00", "Z")


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


def _menu_item_id(client) -> str:
    response = client.get("/api/v1/menu/items")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    return payload[0]["id"]


def _create_address(client, csrf: str, postal_code: str = "10001") -> str:
    response = client.post(
        "/api/v1/addresses",
        headers=_headers(csrf, nonce=f"address-{postal_code}-{datetime.now(UTC).timestamp()}"),
        json={
            "label": "Home",
            "recipient_name": "Student User",
            "line1": "123 Main Street",
            "line2": None,
            "city": "New York",
            "state": "NY",
            "postal_code": postal_code,
            "phone": "555-000-1111",
            "is_default": True,
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_confirmed_order(client, csrf: str, *, order_type: str, slot_start: str, address_id: str | None = None) -> str:
    item_id = _menu_item_id(client)
    created = client.post(
        "/api/v1/orders/drafts",
        headers=_headers(csrf, nonce=f"create-draft-{datetime.now(UTC).timestamp()}"),
        json={
            "order_type": order_type,
            "slot_start": slot_start,
            "address_book_entry_id": address_id,
            "lines": [{"menu_item_id": item_id, "quantity": 1}],
        },
    )
    assert created.status_code == 200
    order_id = created.json()["id"]

    quoted = client.post(
        f"/api/v1/orders/{order_id}/quote",
        headers=_headers(csrf, nonce=f"quote-{order_id}"),
    )
    assert quoted.status_code == 200

    confirmed = client.post(
        f"/api/v1/orders/{order_id}/confirm",
        headers=_headers(csrf, nonce=f"confirm-{order_id}"),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    return order_id


def _transition(client, csrf: str, order_id: str, target_status: str, nonce: str):
    return client.post(
        f"/api/v1/fulfillment/orders/{order_id}/transition",
        headers=_headers(csrf, nonce=nonce),
        json={"target_status": target_status},
    )


def test_pickup_code_verification_valid_invalid_and_expired(client):
    student_csrf = _login(client, "student", "stud123!")
    order_id = _create_confirmed_order(client, student_csrf, order_type="pickup", slot_start=_aligned_slot(60))

    staff_csrf = _login(client, "staff", "staff123!")
    assert _transition(client, staff_csrf, order_id, "preparing", "t-prep").status_code == 200
    assert _transition(client, staff_csrf, order_id, "ready_for_pickup", "t-ready").status_code == 200

    student_csrf = _login(client, "student", "stud123!")
    issued = client.post(f"/api/v1/orders/{order_id}/pickup-code", headers=_headers(student_csrf, nonce="issue-code-1"))
    assert issued.status_code == 200
    code = issued.json()["code"]

    staff_csrf = _login(client, "staff", "staff123!")
    invalid = client.post(
        f"/api/v1/fulfillment/orders/{order_id}/verify-pickup-code",
        headers=_headers(staff_csrf, nonce="verify-invalid"),
        json={"code": "000000"},
    )
    assert invalid.status_code == 422

    with Session(get_engine()) as session:
        order = session.scalar(select(Order).where(Order.id == order_id))
        assert order is not None
        order.pickup_code_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.add(order)
        session.commit()

    expired = client.post(
        f"/api/v1/fulfillment/orders/{order_id}/verify-pickup-code",
        headers=_headers(staff_csrf, nonce="verify-expired"),
        json={"code": code},
    )
    assert expired.status_code == 422
    assert "expired" in expired.json()["error"]["message"].lower()

    student_csrf = _login(client, "student", "stud123!")
    reissued = client.post(f"/api/v1/orders/{order_id}/pickup-code", headers=_headers(student_csrf, nonce="issue-code-2"))
    assert reissued.status_code == 200
    new_code = reissued.json()["code"]
    assert new_code != code

    staff_csrf = _login(client, "staff", "staff123!")
    verified = client.post(
        f"/api/v1/fulfillment/orders/{order_id}/verify-pickup-code",
        headers=_headers(staff_csrf, nonce="verify-valid"),
        json={"code": new_code},
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "handed_off"

    with Session(get_engine()) as session:
        events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.target_id == order_id,
                AuditEvent.action.in_(
                    [
                        "fulfillment.transition",
                        "fulfillment.pickup_code.verify_failed",
                        "fulfillment.pickup_code.verified",
                    ]
                ),
            )
        ).all()
        actions = {event.action for event in events}
        assert "fulfillment.transition" in actions
        assert "fulfillment.pickup_code.verify_failed" in actions
        assert "fulfillment.pickup_code.verified" in actions


def test_service_type_specific_transition_enforcement(client):
    student_csrf = _login(client, "student", "stud123!")
    delivery_address_id = _create_address(client, student_csrf)
    delivery_order = _create_confirmed_order(
        client,
        student_csrf,
        order_type="delivery",
        slot_start=_aligned_slot(75),
        address_id=delivery_address_id,
    )
    pickup_order = _create_confirmed_order(client, student_csrf, order_type="pickup", slot_start=_aligned_slot(90))

    staff_csrf = _login(client, "staff", "staff123!")
    invalid_for_delivery = _transition(client, staff_csrf, delivery_order, "ready_for_pickup", "invalid-delivery")
    assert invalid_for_delivery.status_code == 422

    invalid_for_pickup = _transition(client, staff_csrf, pickup_order, "ready_for_dispatch", "invalid-pickup")
    assert invalid_for_pickup.status_code == 422


def test_delivery_dispatch_and_completion_flow(client):
    student_csrf = _login(client, "student", "stud123!")
    delivery_address_id = _create_address(client, student_csrf)
    delivery_order = _create_confirmed_order(
        client,
        student_csrf,
        order_type="delivery",
        slot_start=_aligned_slot(90),
        address_id=delivery_address_id,
    )

    staff_csrf = _login(client, "staff", "staff123!")
    assert _transition(client, staff_csrf, delivery_order, "preparing", "delivery-prep").json()["status"] == "preparing"
    assert (
        _transition(client, staff_csrf, delivery_order, "ready_for_dispatch", "delivery-ready").json()["status"]
        == "ready_for_dispatch"
    )
    assert (
        _transition(client, staff_csrf, delivery_order, "out_for_delivery", "delivery-route").json()["status"]
        == "out_for_delivery"
    )
    delivered = _transition(client, staff_csrf, delivery_order, "delivered", "delivery-done")
    assert delivered.status_code == 200
    assert delivered.json()["status"] == "delivered"

    queue = client.get("/api/v1/fulfillment/queues/delivery")
    assert queue.status_code == 200
    assert delivery_order not in {row["id"] for row in queue.json()}


def test_queue_state_transition_updates_eta_for_other_orders(client):
    staff_csrf = _login(client, "staff", "staff123!")
    slot_start = _aligned_slot(120)
    set_capacity = client.put(
        "/api/v1/scheduling/slot-capacities",
        headers=_headers(staff_csrf, nonce="eta-capacity-queue"),
        json={"slot_start": slot_start, "capacity": 10},
    )
    assert set_capacity.status_code == 200

    student_csrf = _login(client, "student", "stud123!")
    order_a = _create_confirmed_order(client, student_csrf, order_type="pickup", slot_start=slot_start)

    referee_csrf = _login(client, "referee", "ref123!")
    order_b = _create_confirmed_order(client, referee_csrf, order_type="pickup", slot_start=slot_start)

    staff_csrf = _login(client, "staff", "staff123!")
    prepping = _transition(client, staff_csrf, order_b, "preparing", "eta-prep")
    assert prepping.status_code == 200

    student_csrf = _login(client, "student", "stud123!")
    eta_before = client.get(f"/api/v1/orders/{order_a}")
    assert eta_before.status_code == 200
    before_minutes = eta_before.json()["eta_minutes"]

    staff_csrf = _login(client, "staff", "staff123!")
    ready = _transition(client, staff_csrf, order_b, "ready_for_pickup", "eta-ready")
    assert ready.status_code == 200

    student_csrf = _login(client, "student", "stud123!")
    eta_after = client.get(f"/api/v1/orders/{order_a}")
    assert eta_after.status_code == 200
    after_minutes = eta_after.json()["eta_minutes"]

    assert before_minutes is not None
    assert after_minutes is not None
    assert before_minutes != after_minutes


def test_pickup_queue_lists_confirmed_pickup_orders(client):
    student_csrf = _login(client, "student", "stud123!")
    pickup_order = _create_confirmed_order(client, student_csrf, order_type="pickup", slot_start=_aligned_slot(105))

    _login(client, "staff", "staff123!")
    queue = client.get("/api/v1/fulfillment/queues/pickup")
    assert queue.status_code == 200
    queue_ids = {row["id"] for row in queue.json()}
    assert pickup_order in queue_ids
