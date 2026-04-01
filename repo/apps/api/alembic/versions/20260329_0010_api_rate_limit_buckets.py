"""add api rate limit buckets

Revision ID: 20260329_0010
Revises: 20260329_0009
Create Date: 2026-03-29 23:55:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260329_0010"
down_revision: Union[str, None] = "20260329_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_rate_limit_buckets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scope_type", sa.String(length=16), nullable=False),
        sa.Column("scope_key", sa.String(length=128), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "scope_type",
            "scope_key",
            "window_start",
            name="uq_api_rate_limit_buckets_scope_window",
        ),
    )
    op.create_index("ix_api_rate_limit_buckets_scope_type", "api_rate_limit_buckets", ["scope_type"])
    op.create_index("ix_api_rate_limit_buckets_scope_key", "api_rate_limit_buckets", ["scope_key"])
    op.create_index("ix_api_rate_limit_buckets_window_start", "api_rate_limit_buckets", ["window_start"])


def downgrade() -> None:
    op.drop_index("ix_api_rate_limit_buckets_window_start", table_name="api_rate_limit_buckets")
    op.drop_index("ix_api_rate_limit_buckets_scope_key", table_name="api_rate_limit_buckets")
    op.drop_index("ix_api_rate_limit_buckets_scope_type", table_name="api_rate_limit_buckets")
    op.drop_table("api_rate_limit_buckets")
