from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthorizedMembership, authorize_for_active_context, verify_csrf, verify_replay_headers
from app.authz.abac import AbacResourceAttributes, build_subject_attributes, get_policy_evaluator
from app.authz.rbac import Permission
from app.core.errors import AppError
from app.db.models import AddressBookEntry, DeliveryZone, MenuItem, Order, OrderItem, SlotCapacity
from app.db.session import get_db_session
from app.orders.engine import (
    assert_cancellation_allowed,
    apply_conflict_state,
    calculate_eta_minutes,
    clear_existing_order_items,
    compute_subtotal_cents,
    ensure_slot_alignment,
    filter_orders_for_active_scope,
    get_address_for_user,
    get_order_for_user_scope,
    get_quote_expiry,
    issue_pickup_code,
    is_slot_capacity_conflict,
    recalculate_queue_etas_for_scope,
    resolve_delivery_fee,
    validate_line_items,
    validate_order_mutable,
)
from app.schemas.orders import (
    AddressBookEntryRequest,
    AddressBookEntryResponse,
    DeliveryZoneRequest,
    DeliveryZoneResponse,
    MenuItemResponse,
    OrderCancelRequest,
    OrderDraftCreateRequest,
    OrderLineResponse,
    PickupCodeIssueResponse,
    OrderQuoteResponse,
    OrderResponse,
    SlotCapacityRequest,
    SlotCapacityResponse,
)

menu_router = APIRouter(prefix="/menu", tags=["menu"])
address_router = APIRouter(prefix="/addresses", tags=["addresses"])
scheduling_router = APIRouter(prefix="/scheduling", tags=["scheduling"])
orders_router = APIRouter(prefix="/orders", tags=["orders"])


def _serialize_address(entry: AddressBookEntry) -> AddressBookEntryResponse:
    return AddressBookEntryResponse(
        id=entry.id,
        label=entry.label,
        recipient_name=entry.recipient_name,
        line1=entry.line1,
        line2=entry.line2,
        city=entry.city,
        state=entry.state,
        postal_code=entry.postal_code,
        phone=entry.phone,
        is_default=entry.is_default,
    )


def _serialize_zone(zone: DeliveryZone) -> DeliveryZoneResponse:
    return DeliveryZoneResponse(
        id=zone.id,
        zip_code=zone.zip_code,
        flat_fee_cents=zone.flat_fee_cents,
        is_active=zone.is_active,
    )


def _serialize_slot_capacity(slot: SlotCapacity) -> SlotCapacityResponse:
    return SlotCapacityResponse(id=slot.id, slot_start=slot.slot_start, capacity=slot.capacity)


def _serialize_order_lines(db: Session, order_id: str) -> list[OrderLineResponse]:
    lines = db.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).all()
    if not lines:
        return []
    item_ids = [line.menu_item_id for line in lines]
    menu_items = db.scalars(select(MenuItem).where(MenuItem.id.in_(item_ids))).all()
    name_map = {item.id: item.name for item in menu_items}
    return [
        OrderLineResponse(
            id=line.id,
            menu_item_id=line.menu_item_id,
            item_name=name_map.get(line.menu_item_id, "Unknown item"),
            quantity=line.quantity,
            unit_price_cents=line.unit_price_cents,
            line_total_cents=line.line_total_cents,
        )
        for line in lines
    ]


def _serialize_order(db: Session, order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        status=order.status,
        order_type=order.order_type,
        slot_start=order.slot_start,
        subtotal_cents=order.subtotal_cents,
        delivery_fee_cents=order.delivery_fee_cents,
        total_cents=order.total_cents,
        eta_minutes=order.eta_minutes,
        address_book_entry_id=order.address_book_entry_id,
        delivery_zone_id=order.delivery_zone_id,
        conflict_reason=order.conflict_reason,
        cancel_reason=order.cancel_reason,
        quote_expires_at=order.quote_expires_at,
        confirmed_at=order.confirmed_at,
        preparing_at=order.preparing_at,
        ready_at=order.ready_at,
        dispatched_at=order.dispatched_at,
        handed_off_at=order.handed_off_at,
        delivered_at=order.delivered_at,
        pickup_code_expires_at=order.pickup_code_expires_at,
        pickup_code_rotated_at=order.pickup_code_rotated_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
        lines=_serialize_order_lines(db, order.id),
    )


def _build_quote_response(db: Session, order: Order, *, next_available_slots: list[datetime] | None = None) -> OrderQuoteResponse:
    return OrderQuoteResponse(
        order_id=order.id,
        status=order.status,
        order_type=order.order_type,
        slot_start=order.slot_start,
        subtotal_cents=order.subtotal_cents,
        delivery_fee_cents=order.delivery_fee_cents,
        total_cents=order.total_cents,
        eta_minutes=order.eta_minutes,
        quote_expires_at=order.quote_expires_at,
        lines=_serialize_order_lines(db, order.id),
        next_available_slots=next_available_slots or [],
        conflict_reason=order.conflict_reason,
    )


def _assert_menu_items_for_scope(db: Session, authorized: AuthorizedMembership, menu_item_ids: list[str]) -> dict[str, MenuItem]:
    membership = authorized.membership
    menu_items = db.scalars(
        select(MenuItem).where(
            MenuItem.id.in_(menu_item_ids),
            MenuItem.organization_id == membership.organization_id,
            MenuItem.program_id == membership.program_id,
            MenuItem.event_id == membership.event_id,
            MenuItem.store_id == membership.store_id,
            MenuItem.is_active.is_(True),
        )
    ).all()
    if len(menu_items) != len(set(menu_item_ids)):
        raise AppError(code="VALIDATION_ERROR", message="One or more menu items are invalid for active context", status_code=422)
    return {item.id: item for item in menu_items}


def _populate_order_line_items(
    db: Session,
    order: Order,
    lines_payload,
    menu_map: dict[str, MenuItem],
) -> list[OrderItem]:
    clear_existing_order_items(db, order.id)
    created: list[OrderItem] = []
    for line in lines_payload:
        menu_item = menu_map[line.menu_item_id]
        line_total = menu_item.price_cents * line.quantity
        row = OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            quantity=line.quantity,
            unit_price_cents=menu_item.price_cents,
            line_total_cents=line_total,
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created


def _resolve_order_delivery(
    db: Session,
    authorized: AuthorizedMembership,
    *,
    order_type: str,
    address_book_entry_id: str | None,
) -> tuple[str | None, str | None, int]:
    membership = authorized.membership
    principal = authorized.principal
    if order_type == "pickup":
        return None, None, 0

    if not address_book_entry_id:
        raise AppError(code="VALIDATION_ERROR", message="Delivery orders require address_book_entry_id", status_code=422)

    address = get_address_for_user(
        db,
        address_id=address_book_entry_id,
        user_id=principal.user.id,
        organization_id=membership.organization_id,
    )
    fee_cents, zone = resolve_delivery_fee(db, membership, order_type=order_type, address=address)
    return address.id, zone.id if zone else None, fee_cents


def _quote_or_raise_conflict(db: Session, authorized: AuthorizedMembership, order: Order) -> None:
    membership = authorized.membership
    has_conflict, suggestions = is_slot_capacity_conflict(
        db,
        membership,
        order.slot_start,
        exclude_order_id=order.id,
    )
    if has_conflict:
        apply_conflict_state(order, reason="slot_capacity_exceeded")
        db.add(order)
        db.commit()
        raise AppError(
            code="VALIDATION_ERROR",
            message="Requested slot is at capacity",
            status_code=409,
            details={
                "order_id": order.id,
                "next_slots": [slot.isoformat() for slot in suggestions],
            },
        )


@menu_router.get("/items", response_model=list[MenuItemResponse])
def list_menu_items(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.MENU_VIEW, surface="ordering", action="menu_items")
    ),
    db: Session = Depends(get_db_session),
) -> list[MenuItemResponse]:
    principal = authorized.principal
    membership = authorized.membership
    items = db.scalars(
        select(MenuItem)
        .where(
            MenuItem.organization_id == membership.organization_id,
            MenuItem.program_id == membership.program_id,
            MenuItem.event_id == membership.event_id,
            MenuItem.store_id == membership.store_id,
            MenuItem.is_active.is_(True),
        )
        .order_by(MenuItem.name.asc())
    ).all()

    subject = build_subject_attributes(principal.user)
    row_evaluator = get_policy_evaluator(db, membership, surface="ordering", action="menu_row_view")
    visible_items: list[MenuItem] = []
    for item in items:
        decision = row_evaluator.evaluate(
            subject=subject,
            resource=AbacResourceAttributes(
                department=item.department_scope,
                grade=item.grade_scope,
                class_code=item.class_scope,
            ),
            default_allow_if_no_rules=True,
        )
        if decision.allowed:
            visible_items.append(item)

    return [
        MenuItemResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            price_cents=item.price_cents,
            is_active=item.is_active,
        )
        for item in visible_items
    ]


@address_router.get("", response_model=list[AddressBookEntryResponse])
def list_addresses(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ADDRESS_BOOK_MANAGE_OWN, surface="ordering", action="address_list")
    ),
    db: Session = Depends(get_db_session),
) -> list[AddressBookEntryResponse]:
    principal = authorized.principal
    membership = authorized.membership
    rows = db.scalars(
        select(AddressBookEntry)
        .where(
            AddressBookEntry.user_id == principal.user.id,
            AddressBookEntry.organization_id == membership.organization_id,
        )
        .order_by(AddressBookEntry.is_default.desc(), AddressBookEntry.created_at.asc())
    ).all()
    return [_serialize_address(row) for row in rows]


@address_router.post("", response_model=AddressBookEntryResponse, dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def create_address(
    payload: AddressBookEntryRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ADDRESS_BOOK_MANAGE_OWN, surface="ordering", action="address_create")
    ),
    db: Session = Depends(get_db_session),
) -> AddressBookEntryResponse:
    principal = authorized.principal
    membership = authorized.membership

    if payload.is_default:
        existing_defaults = db.scalars(
            select(AddressBookEntry).where(
                AddressBookEntry.user_id == principal.user.id,
                AddressBookEntry.organization_id == membership.organization_id,
                AddressBookEntry.is_default.is_(True),
            )
        ).all()
        for row in existing_defaults:
            row.is_default = False
            row.updated_at = datetime.now(UTC)
            db.add(row)

    entry = AddressBookEntry(
        user_id=principal.user.id,
        organization_id=membership.organization_id,
        label=payload.label,
        recipient_name=payload.recipient_name,
        line1=payload.line1,
        line2=payload.line2,
        city=payload.city,
        state=payload.state.upper(),
        postal_code=payload.postal_code,
        phone=payload.phone,
        is_default=payload.is_default,
        updated_at=datetime.now(UTC),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _serialize_address(entry)


@address_router.put("/{address_id}", response_model=AddressBookEntryResponse, dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def update_address(
    address_id: str,
    payload: AddressBookEntryRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ADDRESS_BOOK_MANAGE_OWN, surface="ordering", action="address_update")
    ),
    db: Session = Depends(get_db_session),
) -> AddressBookEntryResponse:
    principal = authorized.principal
    membership = authorized.membership
    entry = db.scalar(
        select(AddressBookEntry).where(
            AddressBookEntry.id == address_id,
            AddressBookEntry.user_id == principal.user.id,
            AddressBookEntry.organization_id == membership.organization_id,
        )
    )
    if not entry:
        raise AppError(code="VALIDATION_ERROR", message="Address not found", status_code=404)

    if payload.is_default:
        existing_defaults = db.scalars(
            select(AddressBookEntry).where(
                AddressBookEntry.user_id == principal.user.id,
                AddressBookEntry.organization_id == membership.organization_id,
                AddressBookEntry.is_default.is_(True),
                AddressBookEntry.id != entry.id,
            )
        ).all()
        for row in existing_defaults:
            row.is_default = False
            row.updated_at = datetime.now(UTC)
            db.add(row)

    entry.label = payload.label
    entry.recipient_name = payload.recipient_name
    entry.line1 = payload.line1
    entry.line2 = payload.line2
    entry.city = payload.city
    entry.state = payload.state.upper()
    entry.postal_code = payload.postal_code
    entry.phone = payload.phone
    entry.is_default = payload.is_default
    entry.updated_at = datetime.now(UTC)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _serialize_address(entry)


@address_router.delete("/{address_id}", dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def delete_address(
    address_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ADDRESS_BOOK_MANAGE_OWN, surface="ordering", action="address_delete")
    ),
    db: Session = Depends(get_db_session),
) -> dict:
    principal = authorized.principal
    membership = authorized.membership
    entry = db.scalar(
        select(AddressBookEntry).where(
            AddressBookEntry.id == address_id,
            AddressBookEntry.user_id == principal.user.id,
            AddressBookEntry.organization_id == membership.organization_id,
        )
    )
    if not entry:
        raise AppError(code="VALIDATION_ERROR", message="Address not found", status_code=404)
    db.delete(entry)
    db.commit()
    return {"status": "deleted"}


@scheduling_router.get("/delivery-zones", response_model=list[DeliveryZoneResponse])
def list_delivery_zones(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.SCHEDULING_MANAGE, surface="ordering", action="delivery_zone_list")
    ),
    db: Session = Depends(get_db_session),
) -> list[DeliveryZoneResponse]:
    membership = authorized.membership
    zones = db.scalars(
        select(DeliveryZone)
        .where(
            DeliveryZone.organization_id == membership.organization_id,
            DeliveryZone.program_id == membership.program_id,
            DeliveryZone.event_id == membership.event_id,
            DeliveryZone.store_id == membership.store_id,
        )
        .order_by(DeliveryZone.zip_code.asc())
    ).all()
    return [_serialize_zone(zone) for zone in zones]


@scheduling_router.post(
    "/delivery-zones",
    response_model=DeliveryZoneResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def create_delivery_zone(
    payload: DeliveryZoneRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.SCHEDULING_MANAGE, surface="ordering", action="delivery_zone_manage")
    ),
    db: Session = Depends(get_db_session),
) -> DeliveryZoneResponse:
    membership = authorized.membership
    existing = db.scalar(
        select(DeliveryZone).where(
            DeliveryZone.organization_id == membership.organization_id,
            DeliveryZone.program_id == membership.program_id,
            DeliveryZone.event_id == membership.event_id,
            DeliveryZone.store_id == membership.store_id,
            DeliveryZone.zip_code == payload.zip_code,
        )
    )
    if existing:
        existing.flat_fee_cents = payload.flat_fee_cents
        existing.is_active = payload.is_active
        existing.updated_at = datetime.now(UTC)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _serialize_zone(existing)

    zone = DeliveryZone(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        zip_code=payload.zip_code,
        flat_fee_cents=payload.flat_fee_cents,
        is_active=payload.is_active,
        updated_at=datetime.now(UTC),
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return _serialize_zone(zone)


@scheduling_router.put(
    "/delivery-zones/{zone_id}",
    response_model=DeliveryZoneResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def update_delivery_zone(
    zone_id: str,
    payload: DeliveryZoneRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.SCHEDULING_MANAGE, surface="ordering", action="delivery_zone_manage")
    ),
    db: Session = Depends(get_db_session),
) -> DeliveryZoneResponse:
    membership = authorized.membership
    zone = db.scalar(
        select(DeliveryZone).where(
            DeliveryZone.id == zone_id,
            DeliveryZone.organization_id == membership.organization_id,
            DeliveryZone.program_id == membership.program_id,
            DeliveryZone.event_id == membership.event_id,
            DeliveryZone.store_id == membership.store_id,
        )
    )
    if not zone:
        raise AppError(code="VALIDATION_ERROR", message="Delivery zone not found", status_code=404)

    zone.zip_code = payload.zip_code
    zone.flat_fee_cents = payload.flat_fee_cents
    zone.is_active = payload.is_active
    zone.updated_at = datetime.now(UTC)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return _serialize_zone(zone)


@scheduling_router.delete("/delivery-zones/{zone_id}", dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def delete_delivery_zone(
    zone_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.SCHEDULING_MANAGE, surface="ordering", action="delivery_zone_manage")
    ),
    db: Session = Depends(get_db_session),
) -> dict:
    membership = authorized.membership
    zone = db.scalar(
        select(DeliveryZone).where(
            DeliveryZone.id == zone_id,
            DeliveryZone.organization_id == membership.organization_id,
            DeliveryZone.program_id == membership.program_id,
            DeliveryZone.event_id == membership.event_id,
            DeliveryZone.store_id == membership.store_id,
        )
    )
    if not zone:
        raise AppError(code="VALIDATION_ERROR", message="Delivery zone not found", status_code=404)
    db.delete(zone)
    db.commit()
    return {"status": "deleted"}


@scheduling_router.get("/slot-capacities", response_model=list[SlotCapacityResponse])
def list_slot_capacities(
    for_date: date | None = Query(default=None),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.SCHEDULING_MANAGE, surface="ordering", action="slot_capacity_list")
    ),
    db: Session = Depends(get_db_session),
) -> list[SlotCapacityResponse]:
    membership = authorized.membership
    query = select(SlotCapacity).where(
        SlotCapacity.organization_id == membership.organization_id,
        SlotCapacity.program_id == membership.program_id,
        SlotCapacity.event_id == membership.event_id,
        SlotCapacity.store_id == membership.store_id,
    )
    if for_date:
        start = datetime.combine(for_date, time.min, tzinfo=UTC)
        end = start + timedelta(days=1)
        query = query.where(SlotCapacity.slot_start >= start, SlotCapacity.slot_start < end)
    slots = db.scalars(query.order_by(SlotCapacity.slot_start.asc())).all()
    return [_serialize_slot_capacity(slot) for slot in slots]


@scheduling_router.put(
    "/slot-capacities",
    response_model=SlotCapacityResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def upsert_slot_capacity(
    payload: SlotCapacityRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.SCHEDULING_MANAGE, surface="ordering", action="slot_capacity_manage")
    ),
    db: Session = Depends(get_db_session),
) -> SlotCapacityResponse:
    membership = authorized.membership
    slot_start = ensure_slot_alignment(payload.slot_start)
    existing = db.scalar(
        select(SlotCapacity).where(
            SlotCapacity.organization_id == membership.organization_id,
            SlotCapacity.program_id == membership.program_id,
            SlotCapacity.event_id == membership.event_id,
            SlotCapacity.store_id == membership.store_id,
            SlotCapacity.slot_start == slot_start,
        )
    )

    if existing:
        existing.capacity = payload.capacity
        existing.updated_at = datetime.now(UTC)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _serialize_slot_capacity(existing)

    row = SlotCapacity(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        slot_start=slot_start,
        capacity=payload.capacity,
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_slot_capacity(row)


@scheduling_router.delete("/slot-capacities", dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def delete_slot_capacity(
    slot_start: datetime,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.SCHEDULING_MANAGE, surface="ordering", action="slot_capacity_manage")
    ),
    db: Session = Depends(get_db_session),
) -> dict:
    membership = authorized.membership
    aligned = ensure_slot_alignment(slot_start)
    row = db.scalar(
        select(SlotCapacity).where(
            SlotCapacity.organization_id == membership.organization_id,
            SlotCapacity.program_id == membership.program_id,
            SlotCapacity.event_id == membership.event_id,
            SlotCapacity.store_id == membership.store_id,
            SlotCapacity.slot_start == aligned,
        )
    )
    if not row:
        raise AppError(code="VALIDATION_ERROR", message="Slot capacity not found", status_code=404)
    db.delete(row)
    db.commit()
    return {"status": "deleted"}


@orders_router.post("/drafts", response_model=OrderResponse, dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def create_order_draft(
    payload: OrderDraftCreateRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ORDER_MANAGE_OWN, surface="ordering", action="order_create_draft")
    ),
    db: Session = Depends(get_db_session),
) -> OrderResponse:
    membership = authorized.membership
    principal = authorized.principal

    validate_line_items(payload.lines)
    slot_start = ensure_slot_alignment(payload.slot_start)
    menu_map = _assert_menu_items_for_scope(db, authorized, [line.menu_item_id for line in payload.lines])
    address_id, zone_id, delivery_fee = _resolve_order_delivery(
        db,
        authorized,
        order_type=payload.order_type,
        address_book_entry_id=payload.address_book_entry_id,
    )

    order = Order(
        user_id=principal.user.id,
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        order_type=payload.order_type,
        status="draft",
        slot_start=slot_start,
        address_book_entry_id=address_id,
        delivery_zone_id=zone_id,
        delivery_fee_cents=delivery_fee,
        updated_at=datetime.now(UTC),
    )
    db.add(order)
    db.flush()
    order_items = _populate_order_line_items(db, order, payload.lines, menu_map)
    order.subtotal_cents = compute_subtotal_cents(order_items)
    order.total_cents = order.subtotal_cents + order.delivery_fee_cents
    order.updated_at = datetime.now(UTC)
    db.add(order)
    db.commit()
    db.refresh(order)
    return _serialize_order(db, order)


@orders_router.put("/{order_id}/draft", response_model=OrderResponse, dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def update_order_draft(
    order_id: str,
    payload: OrderDraftCreateRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ORDER_MANAGE_OWN, surface="ordering", action="order_update_draft")
    ),
    db: Session = Depends(get_db_session),
) -> OrderResponse:
    order = get_order_for_user_scope(db, authorized.membership, authorized.principal.user.id, order_id)
    validate_order_mutable(order)

    validate_line_items(payload.lines)
    slot_start = ensure_slot_alignment(payload.slot_start)
    menu_map = _assert_menu_items_for_scope(db, authorized, [line.menu_item_id for line in payload.lines])
    address_id, zone_id, delivery_fee = _resolve_order_delivery(
        db,
        authorized,
        order_type=payload.order_type,
        address_book_entry_id=payload.address_book_entry_id,
    )

    order.order_type = payload.order_type
    order.slot_start = slot_start
    order.address_book_entry_id = address_id
    order.delivery_zone_id = zone_id
    order.delivery_fee_cents = delivery_fee
    order.status = "draft"
    order.conflict_reason = None
    order.quote_expires_at = None
    order.updated_at = datetime.now(UTC)

    order_items = _populate_order_line_items(db, order, payload.lines, menu_map)
    order.subtotal_cents = compute_subtotal_cents(order_items)
    order.total_cents = order.subtotal_cents + order.delivery_fee_cents
    db.add(order)
    db.commit()
    db.refresh(order)
    return _serialize_order(db, order)


@orders_router.get("/mine", response_model=list[OrderResponse])
def list_my_orders(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ORDER_MANAGE_OWN, surface="ordering", action="order_list")
    ),
    db: Session = Depends(get_db_session),
) -> list[OrderResponse]:
    rows = filter_orders_for_active_scope(db, authorized.membership, authorized.principal.user.id)
    return [_serialize_order(db, row) for row in rows]


@orders_router.get("/{order_id}", response_model=OrderResponse)
def get_my_order(
    order_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ORDER_MANAGE_OWN, surface="ordering", action="order_view")
    ),
    db: Session = Depends(get_db_session),
) -> OrderResponse:
    row = get_order_for_user_scope(db, authorized.membership, authorized.principal.user.id, order_id)
    return _serialize_order(db, row)


@orders_router.post(
    "/{order_id}/pickup-code",
    response_model=PickupCodeIssueResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def issue_order_pickup_code(
    order_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ORDER_MANAGE_OWN, surface="ordering", action="order_issue_pickup_code")
    ),
    db: Session = Depends(get_db_session),
) -> PickupCodeIssueResponse:
    order = get_order_for_user_scope(db, authorized.membership, authorized.principal.user.id, order_id)
    code, expires_at = issue_pickup_code(order)
    db.add(order)
    db.commit()
    return PickupCodeIssueResponse(
        order_id=order.id,
        code=code,
        expires_at=expires_at,
        ttl_seconds=max(1, int((expires_at - datetime.now(UTC)).total_seconds())),
    )


@orders_router.post("/{order_id}/quote", response_model=OrderQuoteResponse, dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def quote_order(
    order_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ORDER_MANAGE_OWN, surface="ordering", action="order_quote")
    ),
    db: Session = Depends(get_db_session),
) -> OrderQuoteResponse:
    order = get_order_for_user_scope(db, authorized.membership, authorized.principal.user.id, order_id)
    validate_order_mutable(order)

    _quote_or_raise_conflict(db, authorized, order)

    if order.order_type == "delivery":
        if not order.address_book_entry_id:
            raise AppError(code="VALIDATION_ERROR", message="Delivery order missing address", status_code=422)
        address = get_address_for_user(
            db,
            address_id=order.address_book_entry_id,
            user_id=authorized.principal.user.id,
            organization_id=authorized.membership.organization_id,
        )
        fee, zone = resolve_delivery_fee(
            db,
            authorized.membership,
            order_type="delivery",
            address=address,
        )
        order.delivery_fee_cents = fee
        order.delivery_zone_id = zone.id if zone else None
    else:
        order.delivery_fee_cents = 0
        order.delivery_zone_id = None

    lines = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    order.subtotal_cents = compute_subtotal_cents(lines)
    order.total_cents = order.subtotal_cents + order.delivery_fee_cents
    order.eta_minutes = calculate_eta_minutes(db, authorized.membership, order.slot_start, exclude_order_id=order.id)
    order.status = "quoted"
    order.conflict_reason = None
    order.quote_expires_at = get_quote_expiry()
    order.updated_at = datetime.now(UTC)
    db.add(order)
    db.commit()
    db.refresh(order)
    return _build_quote_response(db, order)


@orders_router.post(
    "/{order_id}/confirm",
    response_model=OrderResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def confirm_order(
    order_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ORDER_MANAGE_OWN, surface="ordering", action="order_confirm")
    ),
    db: Session = Depends(get_db_session),
) -> OrderResponse:
    order = get_order_for_user_scope(db, authorized.membership, authorized.principal.user.id, order_id)
    validate_order_mutable(order)

    _quote_or_raise_conflict(db, authorized, order)

    if order.order_type == "delivery":
        if not order.address_book_entry_id:
            raise AppError(code="VALIDATION_ERROR", message="Delivery order missing address", status_code=422)
        address = get_address_for_user(
            db,
            address_id=order.address_book_entry_id,
            user_id=authorized.principal.user.id,
            organization_id=authorized.membership.organization_id,
        )
        fee, zone = resolve_delivery_fee(
            db,
            authorized.membership,
            order_type="delivery",
            address=address,
        )
        order.delivery_fee_cents = fee
        order.delivery_zone_id = zone.id if zone else None
    else:
        order.delivery_fee_cents = 0
        order.delivery_zone_id = None

    lines = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    order.subtotal_cents = compute_subtotal_cents(lines)
    order.total_cents = order.subtotal_cents + order.delivery_fee_cents
    order.status = "confirmed"
    order.conflict_reason = None
    order.quote_expires_at = None
    order.confirmed_at = datetime.now(UTC)
    order.updated_at = datetime.now(UTC)
    db.add(order)
    db.flush()
    recalculate_queue_etas_for_scope(db, authorized.membership)
    db.commit()
    db.refresh(order)
    return _serialize_order(db, order)


@orders_router.post("/{order_id}/cancel", response_model=OrderResponse, dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def cancel_order(
    order_id: str,
    payload: OrderCancelRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.ORDER_MANAGE_OWN, surface="ordering", action="order_cancel")
    ),
    db: Session = Depends(get_db_session),
) -> OrderResponse:
    order = get_order_for_user_scope(db, authorized.membership, authorized.principal.user.id, order_id)
    if order.status == "cancelled":
        return _serialize_order(db, order)
    assert_cancellation_allowed(order)

    order.status = "cancelled"
    order.cancel_reason = payload.reason
    order.conflict_reason = None
    order.quote_expires_at = None
    order.pickup_code_hash = None
    order.pickup_code_expires_at = None
    order.pickup_code_rotated_at = None
    order.updated_at = datetime.now(UTC)
    db.add(order)
    recalculate_queue_etas_for_scope(db, authorized.membership)
    db.commit()
    db.refresh(order)
    return _serialize_order(db, order)
