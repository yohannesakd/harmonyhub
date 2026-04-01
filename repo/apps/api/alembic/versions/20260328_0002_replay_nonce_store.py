"""add replay nonce store

Revision ID: 20260328_0002
Revises: 20260328_0001
Create Date: 2026-03-28 00:10:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260328_0002"
down_revision: Union[str, None] = "20260328_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "replay_nonces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("nonce", sa.String(length=128), nullable=False, unique=True),
        sa.Column("request_method", sa.String(length=16), nullable=False),
        sa.Column("request_path", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_replay_nonces_nonce", "replay_nonces", ["nonce"])
    op.create_index("ix_replay_nonces_created_at", "replay_nonces", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_replay_nonces_created_at", table_name="replay_nonces")
    op.drop_index("ix_replay_nonces_nonce", table_name="replay_nonces")
    op.drop_table("replay_nonces")
