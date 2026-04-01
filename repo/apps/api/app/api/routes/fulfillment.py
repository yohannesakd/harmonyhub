from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthorizedMembership, authorize_for_active_context, verify_csrf, verify_replay_headers
from app.authz.rbac import Permission
from app.core.errors import AppError
from app.db.models import AddressBookEntry, MenuItem, Order, OrderItem, User
from app.db.session import get_db_session
from app.operations.audit import record_membership_audit_event
from app.orders.engine import (
    FULFILLMENT_DELIVERY_QUEUE_STATUSES,
    FULFILLMENT_PICKUP_QUEUE_STATUSES,
    apply_fulfillment_transition,
    get_order_for_fulfillment_scope,
    mark_pickup_handed_off,
    recalculate_queue_etas_for_scope,
    verify_pickup_code,
)
from app.schemas.fulfillment import (
    FulfillmentAddressSummary,
    FulfillmentQueueOrderResponse,
    FulfillmentTransitionRequest,
    PickupCodeVerifyRequest,
)
from app.schemas.orders import OrderLineResponse, OrderResponse

router = APIRouter(prefix="/fulfillment", tags=["fulfillment"])


def _serialize_order_lines(lines: list[OrderItem], item_names: dict[str, str]) -> list[OrderLineResponse]:
    return [
        OrderLineResponse(
            id=line.id,
            menu_item_id=line.menu_item_id,
            item_name=item_names.get(line.menu_item_id, "Unknown item"),
            quantity=line.quantity,
            unit_price_cents=line.unit_price_cents,
            line_total_cents=line.line_total_cents,
        )
        for line in lines
    ]


def _serialize_order_response(
    order: Order,
    lines: list[OrderLineResponse],
) -> OrderResponse:
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
        lines=lines,
    )


def _build_queue_payloads(db: Session, orders: list[Order]) -> list[FulfillmentQueueOrderResponse]:
    if not orders:
        return []

    order_ids = [row.id for row in orders]
    lines = db.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids))).all()
    lines_by_order: dict[str, list[OrderItem]] = {order_id: [] for order_id in order_ids}
    menu_ids: set[str] = set()
    for line in lines:
        lines_by_order.setdefault(line.order_id, []).append(line)
        menu_ids.add(line.menu_item_id)

    menu_rows = db.scalars(select(MenuItem).where(MenuItem.id.in_(list(menu_ids)))).all() if menu_ids else []
    item_names = {row.id: row.name for row in menu_rows}

    user_ids = list({row.user_id for row in orders})
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    username_by_id = {row.id: row.username for row in users}

    address_ids = [row.address_book_entry_id for row in orders if row.address_book_entry_id]
    addresses = (
        db.scalars(select(AddressBookEntry).where(AddressBookEntry.id.in_(address_ids))).all() if address_ids else []
    )
    address_by_id = {row.id: row for row in addresses}

    payloads: list[FulfillmentQueueOrderResponse] = []
    for order in orders:
        order_lines = _serialize_order_lines(lines_by_order.get(order.id, []), item_names)
        address_summary: FulfillmentAddressSummary | None = None
        if order.address_book_entry_id and order.address_book_entry_id in address_by_id:
            address = address_by_id[order.address_book_entry_id]
            address_summary = FulfillmentAddressSummary(
                recipient_name=address.recipient_name,
                line1=address.line1,
                line2=address.line2,
                city=address.city,
                state=address.state,
                postal_code=address.postal_code,
                phone=address.phone,
            )

        payloads.append(
            FulfillmentQueueOrderResponse(
                id=order.id,
                user_id=order.user_id,
                username=username_by_id.get(order.user_id, "unknown"),
                status=order.status,
                order_type=order.order_type,
                slot_start=order.slot_start,
                subtotal_cents=order.subtotal_cents,
                delivery_fee_cents=order.delivery_fee_cents,
                total_cents=order.total_cents,
                eta_minutes=order.eta_minutes,
                confirmed_at=order.confirmed_at,
                preparing_at=order.preparing_at,
                ready_at=order.ready_at,
                dispatched_at=order.dispatched_at,
                handed_off_at=order.handed_off_at,
                delivered_at=order.delivered_at,
                updated_at=order.updated_at,
                lines=order_lines,
                address=address_summary,
            )
        )
    return payloads


def _record_audit_event(
    db: Session,
    authorized: AuthorizedMembership,
    *,
    action: str,
    order_id: str,
    details: dict,
) -> None:
    record_membership_audit_event(
        db,
        authorized.membership,
        action=action,
        target_type="order",
        target_id=order_id,
        details=details,
    )


@router.get("/queues/pickup", response_model=list[FulfillmentQueueOrderResponse])
def list_pickup_queue(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.FULFILLMENT_MANAGE, surface="fulfillment", action="queue_pickup")
    ),
    db: Session = Depends(get_db_session),
) -> list[FulfillmentQueueOrderResponse]:
    membership = authorized.membership
    orders = db.scalars(
        select(Order)
        .where(
            Order.organization_id == membership.organization_id,
            Order.program_id == membership.program_id,
            Order.event_id == membership.event_id,
            Order.store_id == membership.store_id,
            Order.order_type == "pickup",
            Order.status.in_(FULFILLMENT_PICKUP_QUEUE_STATUSES),
        )
        .order_by(Order.slot_start.asc(), Order.created_at.asc())
    ).all()
    return _build_queue_payloads(db, orders)


@router.get("/queues/delivery", response_model=list[FulfillmentQueueOrderResponse])
def list_delivery_queue(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.FULFILLMENT_MANAGE, surface="fulfillment", action="queue_delivery")
    ),
    db: Session = Depends(get_db_session),
) -> list[FulfillmentQueueOrderResponse]:
    membership = authorized.membership
    orders = db.scalars(
        select(Order)
        .where(
            Order.organization_id == membership.organization_id,
            Order.program_id == membership.program_id,
            Order.event_id == membership.event_id,
            Order.store_id == membership.store_id,
            Order.order_type == "delivery",
            Order.status.in_(FULFILLMENT_DELIVERY_QUEUE_STATUSES),
        )
        .order_by(Order.slot_start.asc(), Order.created_at.asc())
    ).all()
    return _build_queue_payloads(db, orders)


@router.post(
    "/orders/{order_id}/transition",
    response_model=OrderResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def transition_order_status(
    order_id: str,
    payload: FulfillmentTransitionRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.FULFILLMENT_MANAGE, surface="fulfillment", action="transition")
    ),
    db: Session = Depends(get_db_session),
) -> OrderResponse:
    order = get_order_for_fulfillment_scope(db, authorized.membership, order_id)
    old_status = order.status

    apply_fulfillment_transition(order, payload.target_status, cancel_reason=payload.cancel_reason)
    if payload.target_status == "ready_for_pickup":
        # Force fresh issuance per handoff cycle; plaintext pickup code is never persisted.
        order.pickup_code_hash = None
        order.pickup_code_expires_at = None
        order.pickup_code_rotated_at = None

    _record_audit_event(
        db,
        authorized,
        action="fulfillment.transition",
        order_id=order.id,
        details={
            "from_status": old_status,
            "to_status": payload.target_status,
            "order_type": order.order_type,
        },
    )

    db.add(order)
    db.flush()
    recalculate_queue_etas_for_scope(db, authorized.membership)
    db.commit()
    db.refresh(order)

    lines = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    menu_rows = db.scalars(select(MenuItem).where(MenuItem.id.in_([line.menu_item_id for line in lines]))).all()
    item_names = {row.id: row.name for row in menu_rows}
    return _serialize_order_response(order, _serialize_order_lines(lines, item_names))


@router.post(
    "/orders/{order_id}/verify-pickup-code",
    response_model=OrderResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def verify_pickup_code_and_handoff(
    order_id: str,
    payload: PickupCodeVerifyRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.FULFILLMENT_MANAGE, surface="fulfillment", action="verify_pickup_code")
    ),
    db: Session = Depends(get_db_session),
) -> OrderResponse:
    order = get_order_for_fulfillment_scope(db, authorized.membership, order_id)

    try:
        verify_pickup_code(order, payload.code)
    except AppError as exc:
        _record_audit_event(
            db,
            authorized,
            action="fulfillment.pickup_code.verify_failed",
            order_id=order.id,
            details={
                "reason": exc.message,
                "status": order.status,
            },
        )
        db.commit()
        raise

    mark_pickup_handed_off(order)
    _record_audit_event(
        db,
        authorized,
        action="fulfillment.pickup_code.verified",
        order_id=order.id,
        details={
            "verified_at": datetime.now(UTC).isoformat(),
            "order_type": order.order_type,
        },
    )
    db.add(order)
    db.flush()
    recalculate_queue_etas_for_scope(db, authorized.membership)
    db.commit()
    db.refresh(order)

    lines = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    menu_rows = db.scalars(select(MenuItem).where(MenuItem.id.in_([line.menu_item_id for line in lines]))).all()
    item_names = {row.id: row.name for row in menu_rows}
    return _serialize_order_response(order, _serialize_order_lines(lines, item_names))
