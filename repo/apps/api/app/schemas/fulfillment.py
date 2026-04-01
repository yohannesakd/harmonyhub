from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.orders import OrderLineResponse, OrderStatus, OrderType

FulfillmentTransitionStatus = Literal[
    "preparing",
    "ready_for_pickup",
    "ready_for_dispatch",
    "out_for_delivery",
    "delivered",
    "cancelled",
]


class FulfillmentAddressSummary(BaseModel):
    recipient_name: str
    line1: str
    line2: str | None
    city: str
    state: str
    postal_code: str
    phone: str | None


class FulfillmentQueueOrderResponse(BaseModel):
    id: str
    user_id: str
    username: str
    status: OrderStatus
    order_type: OrderType
    slot_start: datetime
    subtotal_cents: int
    delivery_fee_cents: int
    total_cents: int
    eta_minutes: int | None
    confirmed_at: datetime | None
    preparing_at: datetime | None
    ready_at: datetime | None
    dispatched_at: datetime | None
    handed_off_at: datetime | None
    delivered_at: datetime | None
    updated_at: datetime
    lines: list[OrderLineResponse]
    address: FulfillmentAddressSummary | None = None


class FulfillmentTransitionRequest(BaseModel):
    target_status: FulfillmentTransitionStatus
    cancel_reason: str | None = Field(default=None, max_length=255)


class PickupCodeVerifyRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
