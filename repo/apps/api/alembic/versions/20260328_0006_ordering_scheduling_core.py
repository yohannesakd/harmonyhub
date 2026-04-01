"""add ordering and scheduling core tables

Revision ID: 20260328_0006
Revises: 20260328_0005
Create Date: 2026-03-28 19:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260328_0006"
down_revision: Union[str, None] = "20260328_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "menu_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "name",
            name="uq_menu_items_scope_name",
        ),
    )
    op.create_index("ix_menu_items_organization_id", "menu_items", ["organization_id"])
    op.create_index("ix_menu_items_program_id", "menu_items", ["program_id"])
    op.create_index("ix_menu_items_event_id", "menu_items", ["event_id"])
    op.create_index("ix_menu_items_store_id", "menu_items", ["store_id"])

    op.create_table(
        "address_book_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("recipient_name", sa.String(length=120), nullable=False),
        sa.Column("line1", sa.String(length=255), nullable=False),
        sa.Column("line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("postal_code", sa.String(length=10), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_address_book_entries_user_id", "address_book_entries", ["user_id"])
    op.create_index("ix_address_book_entries_organization_id", "address_book_entries", ["organization_id"])
    op.create_index("ix_address_book_entries_postal_code", "address_book_entries", ["postal_code"])

    op.create_table(
        "delivery_zones",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("zip_code", sa.String(length=10), nullable=False),
        sa.Column("flat_fee_cents", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "zip_code",
            name="uq_delivery_zones_scope_zip",
        ),
    )
    op.create_index("ix_delivery_zones_organization_id", "delivery_zones", ["organization_id"])
    op.create_index("ix_delivery_zones_program_id", "delivery_zones", ["program_id"])
    op.create_index("ix_delivery_zones_event_id", "delivery_zones", ["event_id"])
    op.create_index("ix_delivery_zones_store_id", "delivery_zones", ["store_id"])

    op.create_table(
        "slot_capacities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "slot_start",
            name="uq_slot_capacities_scope_slot",
        ),
    )
    op.create_index("ix_slot_capacities_organization_id", "slot_capacities", ["organization_id"])
    op.create_index("ix_slot_capacities_program_id", "slot_capacities", ["program_id"])
    op.create_index("ix_slot_capacities_event_id", "slot_capacities", ["event_id"])
    op.create_index("ix_slot_capacities_store_id", "slot_capacities", ["store_id"])
    op.create_index("ix_slot_capacities_slot_start", "slot_capacities", ["slot_start"])

    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "address_book_entry_id",
            sa.String(length=36),
            sa.ForeignKey("address_book_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("delivery_zone_id", sa.String(length=36), sa.ForeignKey("delivery_zones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("delivery_fee_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("eta_minutes", sa.Integer(), nullable=True),
        sa.Column("quote_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("conflict_reason", sa.String(length=120), nullable=True),
        sa.Column("cancel_reason", sa.String(length=255), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_organization_id", "orders", ["organization_id"])
    op.create_index("ix_orders_program_id", "orders", ["program_id"])
    op.create_index("ix_orders_event_id", "orders", ["event_id"])
    op.create_index("ix_orders_store_id", "orders", ["store_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_slot_start", "orders", ["slot_start"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("menu_item_id", sa.String(length=36), sa.ForeignKey("menu_items.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("line_total_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_menu_item_id", "order_items", ["menu_item_id"])


def downgrade() -> None:
    op.drop_index("ix_order_items_menu_item_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("ix_orders_slot_start", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_store_id", table_name="orders")
    op.drop_index("ix_orders_event_id", table_name="orders")
    op.drop_index("ix_orders_program_id", table_name="orders")
    op.drop_index("ix_orders_organization_id", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_slot_capacities_slot_start", table_name="slot_capacities")
    op.drop_index("ix_slot_capacities_store_id", table_name="slot_capacities")
    op.drop_index("ix_slot_capacities_event_id", table_name="slot_capacities")
    op.drop_index("ix_slot_capacities_program_id", table_name="slot_capacities")
    op.drop_index("ix_slot_capacities_organization_id", table_name="slot_capacities")
    op.drop_table("slot_capacities")

    op.drop_index("ix_delivery_zones_store_id", table_name="delivery_zones")
    op.drop_index("ix_delivery_zones_event_id", table_name="delivery_zones")
    op.drop_index("ix_delivery_zones_program_id", table_name="delivery_zones")
    op.drop_index("ix_delivery_zones_organization_id", table_name="delivery_zones")
    op.drop_table("delivery_zones")

    op.drop_index("ix_address_book_entries_postal_code", table_name="address_book_entries")
    op.drop_index("ix_address_book_entries_organization_id", table_name="address_book_entries")
    op.drop_index("ix_address_book_entries_user_id", table_name="address_book_entries")
    op.drop_table("address_book_entries")

    op.drop_index("ix_menu_items_store_id", table_name="menu_items")
    op.drop_index("ix_menu_items_event_id", table_name="menu_items")
    op.drop_index("ix_menu_items_program_id", table_name="menu_items")
    op.drop_index("ix_menu_items_organization_id", table_name="menu_items")
    op.drop_table("menu_items")
