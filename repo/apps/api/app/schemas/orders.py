from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

OrderType = Literal["pickup", "delivery"]
OrderStatus = Literal[
    "draft",
    "quoted",
    "confirmed",
    "preparing",
    "ready_for_pickup",
    "handed_off",
    "ready_for_dispatch",
    "out_for_delivery",
    "delivered",
    "conflict",
    "cancelled",
]


class MenuItemResponse(BaseModel):
    id: str
    name: str
    description: str | None
    price_cents: int
    is_active: bool


class AddressBookEntryRequest(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    recipient_name: str = Field(min_length=1, max_length=120)
    line1: str = Field(min_length=1, max_length=255)
    line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(pattern="^[A-Za-z]{2}$")
    postal_code: str = Field(pattern=r"^\d{5}(-\d{4})?$")
    phone: str | None = Field(default=None, max_length=20)
    is_default: bool = False


class AddressBookEntryResponse(BaseModel):
    id: str
    label: str
    recipient_name: str
    line1: str
    line2: str | None
    city: str
    state: str
    postal_code: str
    phone: str | None
    is_default: bool


class DeliveryZoneRequest(BaseModel):
    zip_code: str = Field(pattern=r"^\d{5}$")
    flat_fee_cents: int = Field(ge=0, le=10000)
    is_active: bool = True


class DeliveryZoneResponse(BaseModel):
    id: str
    zip_code: str
    flat_fee_cents: int
    is_active: bool


class SlotCapacityRequest(BaseModel):
    slot_start: datetime
    capacity: int = Field(ge=0, le=200)


class SlotCapacityResponse(BaseModel):
    id: str
    slot_start: datetime
    capacity: int


class OrderLineRequest(BaseModel):
    menu_item_id: str
    quantity: int = Field(ge=1, le=50)


class OrderLineResponse(BaseModel):
    id: str
    menu_item_id: str
    item_name: str
    quantity: int
    unit_price_cents: int
    line_total_cents: int


class OrderDraftCreateRequest(BaseModel):
    order_type: OrderType
    slot_start: datetime
    address_book_entry_id: str | None = None
    lines: list[OrderLineRequest] = Field(min_length=1)


class OrderQuoteResponse(BaseModel):
    order_id: str
    status: OrderStatus
    order_type: OrderType
    slot_start: datetime
    subtotal_cents: int
    delivery_fee_cents: int
    total_cents: int
    eta_minutes: int | None
    quote_expires_at: datetime | None
    lines: list[OrderLineResponse]
    next_available_slots: list[datetime] = Field(default_factory=list)
    conflict_reason: str | None = None


class OrderResponse(BaseModel):
    id: str
    status: OrderStatus
    order_type: OrderType
    slot_start: datetime
    subtotal_cents: int
    delivery_fee_cents: int
    total_cents: int
    eta_minutes: int | None
    address_book_entry_id: str | None
    delivery_zone_id: str | None
    conflict_reason: str | None
    cancel_reason: str | None
    quote_expires_at: datetime | None
    confirmed_at: datetime | None
    preparing_at: datetime | None
    ready_at: datetime | None
    dispatched_at: datetime | None
    handed_off_at: datetime | None
    delivered_at: datetime | None
    pickup_code_expires_at: datetime | None
    pickup_code_rotated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[OrderLineResponse]


class OrderCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class PickupCodeIssueResponse(BaseModel):
    order_id: str
    code: str = Field(pattern=r"^\d{6}$")
    expires_at: datetime
    ttl_seconds: int
