"""move account freeze state to memberships

Revision ID: 20260407_0015
Revises: 20260330_0014
Create Date: 2026-04-07 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260407_0015"
down_revision: Union[str, None] = "20260330_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("memberships") as batch:
        batch.add_column(sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch.add_column(sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("freeze_reason", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("frozen_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("unfrozen_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("unfrozen_by_user_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_memberships_frozen_by_user_id", "users", ["frozen_by_user_id"], ["id"])
        batch.create_foreign_key("fk_memberships_unfrozen_by_user_id", "users", ["unfrozen_by_user_id"], ["id"])

    op.execute(
        """
        UPDATE memberships
        SET
            is_frozen = CASE WHEN users.frozen_at IS NULL THEN FALSE ELSE TRUE END,
            frozen_at = users.frozen_at,
            freeze_reason = users.freeze_reason,
            frozen_by_user_id = users.frozen_by_user_id,
            unfrozen_at = users.unfrozen_at,
            unfrozen_by_user_id = users.unfrozen_by_user_id
        FROM users
        WHERE users.id = memberships.user_id
        """
    )

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("fk_users_frozen_by_user_id", "users", type_="foreignkey")
        op.drop_constraint("fk_users_unfrozen_by_user_id", "users", type_="foreignkey")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("frozen_at")
        batch.drop_column("freeze_reason")
        batch.drop_column("frozen_by_user_id")
        batch.drop_column("unfrozen_at")
        batch.drop_column("unfrozen_by_user_id")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("freeze_reason", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("frozen_by_user_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("unfrozen_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("unfrozen_by_user_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_users_frozen_by_user_id", "users", ["frozen_by_user_id"], ["id"])
        batch.create_foreign_key("fk_users_unfrozen_by_user_id", "users", ["unfrozen_by_user_id"], ["id"])

    op.execute(
        """
        UPDATE users
        SET
            frozen_at = (
                SELECT m.frozen_at
                FROM memberships m
                WHERE m.user_id = users.id AND m.is_frozen = TRUE
                ORDER BY m.frozen_at DESC NULLS LAST, m.created_at DESC
                LIMIT 1
            ),
            freeze_reason = (
                SELECT m.freeze_reason
                FROM memberships m
                WHERE m.user_id = users.id AND m.is_frozen = TRUE
                ORDER BY m.frozen_at DESC NULLS LAST, m.created_at DESC
                LIMIT 1
            ),
            frozen_by_user_id = (
                SELECT m.frozen_by_user_id
                FROM memberships m
                WHERE m.user_id = users.id AND m.is_frozen = TRUE
                ORDER BY m.frozen_at DESC NULLS LAST, m.created_at DESC
                LIMIT 1
            ),
            unfrozen_at = (
                SELECT m.unfrozen_at
                FROM memberships m
                WHERE m.user_id = users.id AND m.unfrozen_at IS NOT NULL
                ORDER BY m.unfrozen_at DESC, m.created_at DESC
                LIMIT 1
            ),
            unfrozen_by_user_id = (
                SELECT m.unfrozen_by_user_id
                FROM memberships m
                WHERE m.user_id = users.id AND m.unfrozen_at IS NOT NULL
                ORDER BY m.unfrozen_at DESC, m.created_at DESC
                LIMIT 1
            )
        """
    )

    with op.batch_alter_table("memberships") as batch:
        batch.drop_constraint("fk_memberships_unfrozen_by_user_id", type_="foreignkey")
        batch.drop_constraint("fk_memberships_frozen_by_user_id", type_="foreignkey")
        batch.drop_column("unfrozen_by_user_id")
        batch.drop_column("unfrozen_at")
        batch.drop_column("frozen_by_user_id")
        batch.drop_column("freeze_reason")
        batch.drop_column("frozen_at")
        batch.drop_column("is_frozen")
