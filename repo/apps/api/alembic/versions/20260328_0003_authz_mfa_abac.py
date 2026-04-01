"""add mfa and abac foundation tables

Revision ID: 20260328_0003
Revises: 20260328_0002
Create Date: 2026-03-28 00:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260328_0003"
down_revision: Union[str, None] = "20260328_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_totp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("mfa_totp_secret", sa.String(length=64), nullable=True))

    op.create_table(
        "abac_surface_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("surface", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "surface", name="uq_abac_surface_settings_org_surface"),
    )
    op.create_index("ix_abac_surface_settings_organization_id", "abac_surface_settings", ["organization_id"])

    op.create_table(
        "abac_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("surface", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("role", sa.String(length=32), nullable=True),
        sa.Column("program_id", sa.String(length=36), nullable=True),
        sa.Column("event_id", sa.String(length=36), nullable=True),
        sa.Column("store_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_abac_rules_organization_id", "abac_rules", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_abac_rules_organization_id", table_name="abac_rules")
    op.drop_table("abac_rules")

    op.drop_index("ix_abac_surface_settings_organization_id", table_name="abac_surface_settings")
    op.drop_table("abac_surface_settings")

    op.drop_column("users", "mfa_totp_secret")
    op.drop_column("users", "mfa_totp_enabled")
