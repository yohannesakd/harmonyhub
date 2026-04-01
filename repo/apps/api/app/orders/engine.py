from __future__ import annotations

import hashlib
import hmac
import math
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import AddressBookEntry, Membership, Order, OrderItem, SlotCapacity
from app.schemas.orders import OrderLineRequest, OrderType

DEFAULT_SLOT_CAPACITY = 4
QUOTE_TTL_MINUTES = 15

FINALIZED_STATUSES = {
    "confirmed",
    "preparing",
    "ready_for_pickup",
    "handed_off",
    "ready_for_dispatch",
    "out_for_delivery",
    "delivered",
}

ETA_ACTIVE_STATUSES = {
    "confirmed",
    "preparing",
    "ready_for_pickup",
    "ready_for_dispatch",
    "out_for_delivery",
}

ETA_WORKLOAD_WEIGHTS: dict[str, float] = {
    "confirmed": 1.0,
    "preparing": 1.6,
    "ready_for_pickup": 0.4,
    "ready_for_dispatch": 0.6,
    "out_for_delivery": 0.8,
}

PICKUP_CODE_ELIGIBLE_STATUSES = {"confirmed", "preparing", "ready_for_pickup"}

PICKUP_FULFILLMENT_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"ready_for_pickup", "cancelled"},
    "ready_for_pickup": {"cancelled"},
}

DELIVERY_FULFILLMENT_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"ready_for_dispatch", "cancelled"},
    "ready_for_dispatch": {"out_for_delivery", "cancelled"},
    "out_for_delivery": {"delivered"},
}

FULFILLMENT_PICKUP_QUEUE_STATUSES = ["confirmed", "preparing", "ready_for_pickup"]
FULFILLMENT_DELIVERY_QUEUE_STATUSES = ["confirmed", "preparing", "ready_for_dispatch", "out_for_delivery"]


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def ensure_slot_alignment(slot_start: datetime) -> datetime:
    slot_start = to_utc(slot_start)
    if slot_start.minute % 15 != 0 or slot_start.second != 0 or slot_start.microsecond != 0:
        raise AppError(
            code="VALIDATION_ERROR",
            message="slot_start must align to 15-minute boundaries",
            status_code=422,
        )
    return slot_start


def get_slot_capacity(db: Session, membership: Membership, slot_start: datetime) -> int:
    slot = db.scalar(
        select(SlotCapacity).where(
            SlotCapacity.organization_id == membership.organization_id,
            SlotCapacity.program_id == membership.program_id,
            SlotCapacity.event_id == membership.event_id,
            SlotCapacity.store_id == membership.store_id,
            SlotCapacity.slot_start == slot_start,
        )
    )
    return slot.capacity if slot else DEFAULT_SLOT_CAPACITY


def get_confirmed_count_for_slot(
    db: Session,
    membership: Membership,
    slot_start: datetime,
    *,
    exclude_order_id: str | None = None,
) -> int:
    stmt = select(func.count(Order.id)).where(
        Order.organization_id == membership.organization_id,
        Order.program_id == membership.program_id,
        Order.event_id == membership.event_id,
        Order.store_id == membership.store_id,
        Order.status.in_(FINALIZED_STATUSES),
        Order.slot_start == slot_start,
    )
    if exclude_order_id:
        stmt = stmt.where(Order.id != exclude_order_id)
    return int(db.scalar(stmt) or 0)


def has_capacity_for_slot(
    db: Session,
    membership: Membership,
    slot_start: datetime,
    *,
    exclude_order_id: str | None = None,
) -> bool:
    capacity = get_slot_capacity(db, membership, slot_start)
    confirmed_count = get_confirmed_count_for_slot(db, membership, slot_start, exclude_order_id=exclude_order_id)
    return confirmed_count < capacity


def suggest_next_available_slots(
    db: Session,
    membership: Membership,
    slot_start: datetime,
    *,
    exclude_order_id: str | None = None,
    max_suggestions: int = 3,
    scan_slots: int = 24,
) -> list[datetime]:
    suggestions: list[datetime] = []
    current = slot_start + timedelta(minutes=15)
    for _ in range(scan_slots):
        if has_capacity_for_slot(db, membership, current, exclude_order_id=exclude_order_id):
            suggestions.append(current)
            if len(suggestions) >= max_suggestions:
                break
        current += timedelta(minutes=15)
    return suggestions


def resolve_delivery_fee(
    db: Session,
    membership: Membership,
    *,
    order_type: str,
    address: AddressBookEntry | None,
) -> tuple[int, object | None]:
    from app.db.models import DeliveryZone

    if order_type == "pickup":
        return 0, None

    if order_type != "delivery":
        raise AppError(code="VALIDATION_ERROR", message="Invalid order_type", status_code=422)

    if not address:
        raise AppError(code="VALIDATION_ERROR", message="Delivery orders require an address", status_code=422)

    zip_code = address.postal_code[:5]
    zone = db.scalar(
        select(DeliveryZone).where(
            DeliveryZone.organization_id == membership.organization_id,
            DeliveryZone.program_id == membership.program_id,
            DeliveryZone.event_id == membership.event_id,
            DeliveryZone.store_id == membership.store_id,
            DeliveryZone.zip_code == zip_code,
            DeliveryZone.is_active.is_(True),
        )
    )
    if not zone:
        raise AppError(
            code="VALIDATION_ERROR",
            message="Address ZIP is outside active delivery zones",
            status_code=422,
            details={"zip_code": zip_code},
        )

    return zone.flat_fee_cents, zone


def compute_subtotal_cents(order_items: list[OrderItem]) -> int:
    return sum(item.line_total_cents for item in order_items)


def calculate_eta_minutes(
    db: Session,
    membership: Membership,
    slot_start: datetime,
    *,
    exclude_order_id: str | None = None,
) -> int:
    slot_start = to_utc(slot_start)
    now = datetime.now(UTC)

    active_orders_stmt = select(Order.id, Order.slot_start, Order.status).where(
        Order.organization_id == membership.organization_id,
        Order.program_id == membership.program_id,
        Order.event_id == membership.event_id,
        Order.store_id == membership.store_id,
        Order.status.in_(ETA_ACTIVE_STATUSES),
    )
    if exclude_order_id:
        active_orders_stmt = active_orders_stmt.where(Order.id != exclude_order_id)

    rows = db.execute(active_orders_stmt).all()

    queue_workload = 0.0
    backlog_workload = 0.0
    for _, row_slot_start, row_status in rows:
        normalized_slot = to_utc(row_slot_start)
        weight = ETA_WORKLOAD_WEIGHTS.get(row_status, 1.0)
        if normalized_slot >= now:
            queue_workload += weight
        if now <= normalized_slot <= slot_start:
            backlog_workload += weight

    recent_volume_stmt = select(func.count(Order.id)).where(
        Order.organization_id == membership.organization_id,
        Order.program_id == membership.program_id,
        Order.event_id == membership.event_id,
        Order.store_id == membership.store_id,
        Order.status.in_({"confirmed", "preparing", "ready_for_pickup", "ready_for_dispatch", "out_for_delivery"}),
        Order.updated_at >= now - timedelta(hours=72),
    )
    if exclude_order_id:
        recent_volume_stmt = recent_volume_stmt.where(Order.id != exclude_order_id)
    recent_volume = int(db.scalar(recent_volume_stmt) or 0)

    base_minutes = 8
    queue_component = math.ceil(queue_workload * 2.7)
    backlog_component = math.ceil(backlog_workload * 2.2)
    volume_component = min(18, recent_volume)

    slot_distance_component = min(20, max(0, math.ceil((slot_start - now).total_seconds() / 60)))
    return base_minutes + queue_component + backlog_component + volume_component + slot_distance_component


def recalculate_queue_etas_for_scope(db: Session, membership: Membership) -> None:
    scoped_orders = db.scalars(
        select(Order)
        .where(
            Order.organization_id == membership.organization_id,
            Order.program_id == membership.program_id,
            Order.event_id == membership.event_id,
            Order.store_id == membership.store_id,
            Order.status.in_(ETA_ACTIVE_STATUSES),
        )
        .order_by(Order.slot_start.asc(), Order.created_at.asc())
    ).all()

    now = datetime.now(UTC)
    for order in scoped_orders:
        order.eta_minutes = calculate_eta_minutes(db, membership, order.slot_start, exclude_order_id=order.id)
        order.updated_at = now
        db.add(order)


def apply_conflict_state(
    order: Order,
    *,
    reason: str,
) -> None:
    order.status = "conflict"
    order.conflict_reason = reason
    order.updated_at = datetime.now(UTC)


def validate_order_mutable(order: Order) -> None:
    if order.status not in {"draft", "quoted", "conflict"}:
        raise AppError(code="VALIDATION_ERROR", message="Order can no longer be modified", status_code=422)


def clear_existing_order_items(db: Session, order_id: str) -> None:
    existing = db.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).all()
    for row in existing:
        db.delete(row)


def validate_line_items(lines: list[OrderLineRequest]) -> None:
    if not lines:
        raise AppError(code="VALIDATION_ERROR", message="Order requires at least one line item", status_code=422)
    seen: set[str] = set()
    for line in lines:
        if line.menu_item_id in seen:
            raise AppError(code="VALIDATION_ERROR", message="Duplicate menu items are not allowed", status_code=422)
        seen.add(line.menu_item_id)


def get_quote_expiry(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return current + timedelta(minutes=QUOTE_TTL_MINUTES)


def get_address_for_user(
    db: Session,
    *,
    address_id: str,
    user_id: str,
    organization_id: str,
) -> AddressBookEntry:
    address = db.scalar(
        select(AddressBookEntry).where(
            AddressBookEntry.id == address_id,
            AddressBookEntry.user_id == user_id,
            AddressBookEntry.organization_id == organization_id,
        )
    )
    if not address:
        raise AppError(code="VALIDATION_ERROR", message="Address not found", status_code=404)
    return address


def filter_orders_for_active_scope(db: Session, membership: Membership, user_id: str) -> list[Order]:
    return db.scalars(
        select(Order)
        .where(
            Order.user_id == user_id,
            Order.organization_id == membership.organization_id,
            Order.program_id == membership.program_id,
            Order.event_id == membership.event_id,
            Order.store_id == membership.store_id,
        )
        .order_by(Order.created_at.desc())
    ).all()


def get_order_for_user_scope(db: Session, membership: Membership, user_id: str, order_id: str) -> Order:
    order = db.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.user_id == user_id,
            Order.organization_id == membership.organization_id,
            Order.program_id == membership.program_id,
            Order.event_id == membership.event_id,
            Order.store_id == membership.store_id,
        )
    )
    if not order:
        raise AppError(code="VALIDATION_ERROR", message="Order not found", status_code=404)
    return order


def get_order_for_fulfillment_scope(db: Session, membership: Membership, order_id: str) -> Order:
    order = db.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.organization_id == membership.organization_id,
            Order.program_id == membership.program_id,
            Order.event_id == membership.event_id,
            Order.store_id == membership.store_id,
        )
    )
    if not order:
        raise AppError(code="VALIDATION_ERROR", message="Order not found in active context", status_code=404)
    return order


def is_slot_capacity_conflict(
    db: Session,
    membership: Membership,
    slot_start: datetime,
    *,
    exclude_order_id: str | None,
) -> tuple[bool, list[datetime]]:
    if has_capacity_for_slot(db, membership, slot_start, exclude_order_id=exclude_order_id):
        return False, []
    return True, suggest_next_available_slots(db, membership, slot_start, exclude_order_id=exclude_order_id)


def assert_cancellation_allowed(order: Order) -> None:
    if order.status in {"cancelled", "handed_off", "out_for_delivery", "delivered"}:
        raise AppError(code="VALIDATION_ERROR", message="Order can no longer be cancelled", status_code=422)

    cutoff = datetime.now(UTC) - timedelta(hours=6)
    if order.confirmed_at and to_utc(order.confirmed_at) <= cutoff:
        raise AppError(code="VALIDATION_ERROR", message="Order can no longer be cancelled", status_code=422)


def _transition_map_for_type(order_type: OrderType) -> dict[str, set[str]]:
    if order_type == "pickup":
        return PICKUP_FULFILLMENT_TRANSITIONS
    return DELIVERY_FULFILLMENT_TRANSITIONS


def assert_transition_allowed(order: Order, target_status: str) -> None:
    if target_status == "handed_off":
        raise AppError(
            code="VALIDATION_ERROR",
            message="Pickup handoff must be completed via pickup-code verification",
            status_code=422,
        )

    transition_map = _transition_map_for_type(order.order_type)  # type: ignore[arg-type]
    allowed_targets = transition_map.get(order.status, set())
    if target_status not in allowed_targets:
        raise AppError(
            code="VALIDATION_ERROR",
            message=f"Transition from {order.status} to {target_status} is not allowed",
            status_code=422,
        )


def apply_fulfillment_transition(order: Order, target_status: str, *, cancel_reason: str | None = None) -> None:
    assert_transition_allowed(order, target_status)

    now = datetime.now(UTC)
    order.status = target_status
    order.updated_at = now
    order.conflict_reason = None

    if target_status == "preparing":
        order.preparing_at = now
    elif target_status in {"ready_for_pickup", "ready_for_dispatch"}:
        order.ready_at = now
    elif target_status == "out_for_delivery":
        order.dispatched_at = now
    elif target_status == "delivered":
        order.delivered_at = now
    elif target_status == "cancelled":
        order.cancel_reason = cancel_reason


def _pickup_code_secret() -> bytes:
    settings = get_settings()
    return settings.jwt_secret.encode("utf-8")


def _pickup_code_ttl_seconds() -> int:
    settings = get_settings()
    return max(60, settings.pickup_code_ttl_seconds)


def _hash_pickup_code(order_id: str, code: str) -> str:
    payload = f"{order_id}:{code}".encode("utf-8")
    return hmac.new(_pickup_code_secret(), payload, hashlib.sha256).hexdigest()


def generate_pickup_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_pickup_code(order: Order) -> tuple[str, datetime]:
    if order.order_type != "pickup":
        raise AppError(code="VALIDATION_ERROR", message="Pickup code is only available for pickup orders", status_code=422)
    if order.status not in PICKUP_CODE_ELIGIBLE_STATUSES:
        raise AppError(code="VALIDATION_ERROR", message="Order is not eligible for pickup code", status_code=422)

    now = datetime.now(UTC)
    ttl_seconds = _pickup_code_ttl_seconds()
    code = generate_pickup_code()
    order.pickup_code_hash = _hash_pickup_code(order.id, code)
    order.pickup_code_expires_at = now + timedelta(seconds=ttl_seconds)
    order.pickup_code_rotated_at = now
    order.updated_at = now
    return code, order.pickup_code_expires_at


def verify_pickup_code(order: Order, submitted_code: str) -> None:
    if order.order_type != "pickup":
        raise AppError(code="VALIDATION_ERROR", message="Pickup code verification only applies to pickup orders", status_code=422)
    if order.status != "ready_for_pickup":
        raise AppError(code="VALIDATION_ERROR", message="Order is not ready for pickup handoff", status_code=422)
    if not order.pickup_code_hash or not order.pickup_code_expires_at:
        raise AppError(code="VALIDATION_ERROR", message="Pickup code is missing or expired", status_code=422)
    if to_utc(order.pickup_code_expires_at) < datetime.now(UTC):
        raise AppError(code="VALIDATION_ERROR", message="Pickup code has expired", status_code=422)

    expected = _hash_pickup_code(order.id, submitted_code)
    if not hmac.compare_digest(order.pickup_code_hash, expected):
        raise AppError(code="VALIDATION_ERROR", message="Pickup code is invalid", status_code=422)


def mark_pickup_handed_off(order: Order) -> None:
    now = datetime.now(UTC)
    order.status = "handed_off"
    order.handed_off_at = now
    order.pickup_code_hash = None
    order.pickup_code_expires_at = None
    order.pickup_code_rotated_at = None
    order.updated_at = now
