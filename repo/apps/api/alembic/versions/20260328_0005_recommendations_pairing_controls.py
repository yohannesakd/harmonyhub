"""add recommendations and pairing control tables

Revision ID: 20260328_0005
Revises: 20260328_0004
Create Date: 2026-03-28 18:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260328_0005"
down_revision: Union[str, None] = "20260328_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=True),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
        sa.Column("enabled_popularity_30d", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("enabled_recent_activity_72h", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("enabled_tag_match", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("weight_popularity_30d", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("weight_recent_activity_72h", sa.Float(), nullable=False, server_default=sa.text("0.3")),
        sa.Column("weight_tag_match", sa.Float(), nullable=False, server_default=sa.text("0.2")),
        sa.Column("pins_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_pins", sa.Integer(), nullable=False, server_default=sa.text("20")),
        sa.Column("pin_ttl_hours", sa.Integer(), nullable=True),
        sa.Column("enforce_pairing_rules", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_staff_event_store_manage", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            name="uq_recommendation_configs_scope",
        ),
    )
    op.create_index("ix_recommendation_configs_organization_id", "recommendation_configs", ["organization_id"])
    op.create_index("ix_recommendation_configs_program_id", "recommendation_configs", ["program_id"])
    op.create_index("ix_recommendation_configs_event_id", "recommendation_configs", ["event_id"])
    op.create_index("ix_recommendation_configs_store_id", "recommendation_configs", ["store_id"])

    op.create_table(
        "recommendation_signals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("surface", sa.String(length=16), nullable=False),
        sa.Column(
            "directory_entry_id",
            sa.String(length=36),
            sa.ForeignKey("directory_entries.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "repertoire_item_id",
            sa.String(length=36),
            sa.ForeignKey("repertoire_items.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("signal_type", sa.String(length=32), nullable=False, server_default=sa.text("'interaction'")),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recommendation_signals_organization_id", "recommendation_signals", ["organization_id"])
    op.create_index("ix_recommendation_signals_program_id", "recommendation_signals", ["program_id"])
    op.create_index("ix_recommendation_signals_event_id", "recommendation_signals", ["event_id"])
    op.create_index("ix_recommendation_signals_store_id", "recommendation_signals", ["store_id"])
    op.create_index("ix_recommendation_signals_surface", "recommendation_signals", ["surface"])
    op.create_index("ix_recommendation_signals_directory_entry_id", "recommendation_signals", ["directory_entry_id"])
    op.create_index("ix_recommendation_signals_repertoire_item_id", "recommendation_signals", ["repertoire_item_id"])
    op.create_index("ix_recommendation_signals_occurred_at", "recommendation_signals", ["occurred_at"])

    op.create_table(
        "recommendation_featured_pins",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("surface", sa.String(length=16), nullable=False),
        sa.Column(
            "directory_entry_id",
            sa.String(length=36),
            sa.ForeignKey("directory_entries.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "repertoire_item_id",
            sa.String(length=36),
            sa.ForeignKey("repertoire_items.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("pinned_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "surface",
            "directory_entry_id",
            "repertoire_item_id",
            name="uq_recommendation_featured_pins_target",
        ),
    )
    op.create_index("ix_recommendation_featured_pins_organization_id", "recommendation_featured_pins", ["organization_id"])
    op.create_index("ix_recommendation_featured_pins_program_id", "recommendation_featured_pins", ["program_id"])
    op.create_index("ix_recommendation_featured_pins_event_id", "recommendation_featured_pins", ["event_id"])
    op.create_index("ix_recommendation_featured_pins_store_id", "recommendation_featured_pins", ["store_id"])
    op.create_index("ix_recommendation_featured_pins_surface", "recommendation_featured_pins", ["surface"])
    op.create_index(
        "ix_recommendation_featured_pins_directory_entry_id",
        "recommendation_featured_pins",
        ["directory_entry_id"],
    )
    op.create_index(
        "ix_recommendation_featured_pins_repertoire_item_id",
        "recommendation_featured_pins",
        ["repertoire_item_id"],
    )
    op.create_index("ix_recommendation_featured_pins_created_at", "recommendation_featured_pins", ["created_at"])

    op.create_table(
        "pairing_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column(
            "directory_entry_id",
            sa.String(length=36),
            sa.ForeignKey("directory_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repertoire_item_id",
            sa.String(length=36),
            sa.ForeignKey("repertoire_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "program_id",
            "event_id",
            "store_id",
            "directory_entry_id",
            "repertoire_item_id",
            "effect",
            name="uq_pairing_rules_scope_pair_effect",
        ),
    )
    op.create_index("ix_pairing_rules_organization_id", "pairing_rules", ["organization_id"])
    op.create_index("ix_pairing_rules_program_id", "pairing_rules", ["program_id"])
    op.create_index("ix_pairing_rules_event_id", "pairing_rules", ["event_id"])
    op.create_index("ix_pairing_rules_store_id", "pairing_rules", ["store_id"])
    op.create_index("ix_pairing_rules_directory_entry_id", "pairing_rules", ["directory_entry_id"])
    op.create_index("ix_pairing_rules_repertoire_item_id", "pairing_rules", ["repertoire_item_id"])
    op.create_index("ix_pairing_rules_effect", "pairing_rules", ["effect"])


def downgrade() -> None:
    op.drop_index("ix_pairing_rules_effect", table_name="pairing_rules")
    op.drop_index("ix_pairing_rules_repertoire_item_id", table_name="pairing_rules")
    op.drop_index("ix_pairing_rules_directory_entry_id", table_name="pairing_rules")
    op.drop_index("ix_pairing_rules_store_id", table_name="pairing_rules")
    op.drop_index("ix_pairing_rules_event_id", table_name="pairing_rules")
    op.drop_index("ix_pairing_rules_program_id", table_name="pairing_rules")
    op.drop_index("ix_pairing_rules_organization_id", table_name="pairing_rules")
    op.drop_table("pairing_rules")

    op.drop_index("ix_recommendation_featured_pins_created_at", table_name="recommendation_featured_pins")
    op.drop_index("ix_recommendation_featured_pins_repertoire_item_id", table_name="recommendation_featured_pins")
    op.drop_index("ix_recommendation_featured_pins_directory_entry_id", table_name="recommendation_featured_pins")
    op.drop_index("ix_recommendation_featured_pins_surface", table_name="recommendation_featured_pins")
    op.drop_index("ix_recommendation_featured_pins_store_id", table_name="recommendation_featured_pins")
    op.drop_index("ix_recommendation_featured_pins_event_id", table_name="recommendation_featured_pins")
    op.drop_index("ix_recommendation_featured_pins_program_id", table_name="recommendation_featured_pins")
    op.drop_index("ix_recommendation_featured_pins_organization_id", table_name="recommendation_featured_pins")
    op.drop_table("recommendation_featured_pins")

    op.drop_index("ix_recommendation_signals_occurred_at", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_repertoire_item_id", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_directory_entry_id", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_surface", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_store_id", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_event_id", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_program_id", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_organization_id", table_name="recommendation_signals")
    op.drop_table("recommendation_signals")

    op.drop_index("ix_recommendation_configs_store_id", table_name="recommendation_configs")
    op.drop_index("ix_recommendation_configs_event_id", table_name="recommendation_configs")
    op.drop_index("ix_recommendation_configs_program_id", table_name="recommendation_configs")
    op.drop_index("ix_recommendation_configs_organization_id", table_name="recommendation_configs")
    op.drop_table("recommendation_configs")
