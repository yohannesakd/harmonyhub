"""add fulfillment and pickup-code lifecycle columns

Revision ID: 20260328_0007
Revises: 20260328_0006
Create Date: 2026-03-28 20:05:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260328_0007"
down_revision: Union[str, None] = "20260328_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("preparing_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("handed_off_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("pickup_code_hash", sa.String(length=128), nullable=True))
    op.add_column("orders", sa.Column("pickup_code_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("pickup_code_rotated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "pickup_code_rotated_at")
    op.drop_column("orders", "pickup_code_expires_at")
    op.drop_column("orders", "pickup_code_hash")
    op.drop_column("orders", "delivered_at")
    op.drop_column("orders", "handed_off_at")
    op.drop_column("orders", "dispatched_at")
    op.drop_column("orders", "ready_at")
    op.drop_column("orders", "preparing_at")
