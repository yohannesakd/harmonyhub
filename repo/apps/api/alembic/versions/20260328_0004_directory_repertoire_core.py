"""add directory and repertoire core tables

Revision ID: 20260328_0004
Revises: 20260328_0003
Create Date: 2026-03-28 17:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260328_0004"
down_revision: Union[str, None] = "20260328_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "directory_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("stage_name", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("biography", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_directory_entries_scope",
        "directory_entries",
        ["organization_id", "program_id", "event_id", "store_id"],
    )
    op.create_index("ix_directory_entries_display_name", "directory_entries", ["display_name"])
    op.create_index("ix_directory_entries_region", "directory_entries", ["region"])

    op.create_table(
        "repertoire_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("composer", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_repertoire_items_scope",
        "repertoire_items",
        ["organization_id", "program_id", "event_id", "store_id"],
    )
    op.create_index("ix_repertoire_items_title", "repertoire_items", ["title"])
    op.create_index("ix_repertoire_items_composer", "repertoire_items", ["composer"])

    op.create_table(
        "tags",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_tags_org_name"),
    )
    op.create_index("ix_tags_organization_id", "tags", ["organization_id"])
    op.create_index("ix_tags_name", "tags", ["name"])

    op.create_table(
        "directory_entry_tags",
        sa.Column(
            "directory_entry_id",
            sa.String(length=36),
            sa.ForeignKey("directory_entries.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tag_id", sa.String(length=36), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_directory_entry_tags_tag_id", "directory_entry_tags", ["tag_id"])

    op.create_table(
        "repertoire_item_tags",
        sa.Column(
            "repertoire_item_id",
            sa.String(length=36),
            sa.ForeignKey("repertoire_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tag_id", sa.String(length=36), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_repertoire_item_tags_tag_id", "repertoire_item_tags", ["tag_id"])

    op.create_table(
        "directory_entry_repertoire_items",
        sa.Column(
            "directory_entry_id",
            sa.String(length=36),
            sa.ForeignKey("directory_entries.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "repertoire_item_id",
            sa.String(length=36),
            sa.ForeignKey("repertoire_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_directory_entry_repertoire_items_repertoire_item_id",
        "directory_entry_repertoire_items",
        ["repertoire_item_id"],
    )

    op.create_table(
        "availability_windows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "directory_entry_id",
            sa.String(length=36),
            sa.ForeignKey("directory_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_availability_windows_directory_entry_id", "availability_windows", ["directory_entry_id"])
    op.create_index("ix_availability_windows_starts_at", "availability_windows", ["starts_at"])
    op.create_index("ix_availability_windows_ends_at", "availability_windows", ["ends_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=True),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
        sa.Column("actor_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_availability_windows_ends_at", table_name="availability_windows")
    op.drop_index("ix_availability_windows_starts_at", table_name="availability_windows")
    op.drop_index("ix_availability_windows_directory_entry_id", table_name="availability_windows")
    op.drop_table("availability_windows")

    op.drop_index(
        "ix_directory_entry_repertoire_items_repertoire_item_id",
        table_name="directory_entry_repertoire_items",
    )
    op.drop_table("directory_entry_repertoire_items")

    op.drop_index("ix_repertoire_item_tags_tag_id", table_name="repertoire_item_tags")
    op.drop_table("repertoire_item_tags")

    op.drop_index("ix_directory_entry_tags_tag_id", table_name="directory_entry_tags")
    op.drop_table("directory_entry_tags")

    op.drop_index("ix_tags_name", table_name="tags")
    op.drop_index("ix_tags_organization_id", table_name="tags")
    op.drop_table("tags")

    op.drop_index("ix_repertoire_items_composer", table_name="repertoire_items")
    op.drop_index("ix_repertoire_items_title", table_name="repertoire_items")
    op.drop_index("ix_repertoire_items_scope", table_name="repertoire_items")
    op.drop_table("repertoire_items")

    op.drop_index("ix_directory_entries_region", table_name="directory_entries")
    op.drop_index("ix_directory_entries_display_name", table_name="directory_entries")
    op.drop_index("ix_directory_entries_scope", table_name="directory_entries")
    op.drop_table("directory_entries")
