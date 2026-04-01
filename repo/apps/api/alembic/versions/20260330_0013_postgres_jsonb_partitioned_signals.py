"""align json storage to PostgreSQL JSONB and partition recommendation signals

Revision ID: 20260330_0013
Revises: 20260330_0012
Create Date: 2026-03-30 09:15:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260330_0013"
down_revision: Union[str, None] = "20260330_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


JSON_DOCUMENT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("audit_events", "details_json"),
    ("import_batches", "validation_issues_json"),
    ("import_normalized_rows", "raw_row_json"),
    ("import_normalized_rows", "normalized_json"),
    ("import_normalized_rows", "issues_json"),
    ("import_merge_actions", "before_snapshot_json"),
    ("import_merge_actions", "applied_changes_json"),
    ("export_runs", "filters_json"),
    ("backup_runs", "verification_json"),
    ("recovery_drill_runs", "evidence_json"),
)


def _create_recommendation_signal_indexes() -> None:
    op.create_index(
        "ix_recommendation_signals_scope_surface_time",
        "recommendation_signals",
        ["organization_id", "program_id", "event_id", "store_id", "surface", "occurred_at"],
    )
    op.create_index(
        "ix_recommendation_signals_directory_time",
        "recommendation_signals",
        ["directory_entry_id", "occurred_at"],
    )
    op.create_index(
        "ix_recommendation_signals_repertoire_time",
        "recommendation_signals",
        ["repertoire_item_id", "occurred_at"],
    )
    op.create_index(
        "ix_recommendation_signals_user_time",
        "recommendation_signals",
        ["user_id", "occurred_at"],
    )


def _drop_recommendation_signal_indexes() -> None:
    op.drop_index("ix_recommendation_signals_user_time", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_repertoire_time", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_directory_time", table_name="recommendation_signals")
    op.drop_index("ix_recommendation_signals_scope_surface_time", table_name="recommendation_signals")


def _upgrade_postgresql_recommendation_signals() -> None:
    op.execute("ALTER TABLE recommendation_signals RENAME TO recommendation_signals_unpartitioned")

    op.execute(
        """
        CREATE TABLE recommendation_signals (
            id VARCHAR(36) NOT NULL,
            organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id),
            program_id VARCHAR(36) NOT NULL REFERENCES programs(id),
            event_id VARCHAR(36) NOT NULL REFERENCES events(id),
            store_id VARCHAR(36) NOT NULL REFERENCES stores(id),
            surface VARCHAR(16) NOT NULL,
            user_id VARCHAR(36) REFERENCES users(id),
            directory_entry_id VARCHAR(36) REFERENCES directory_entries(id) ON DELETE CASCADE,
            repertoire_item_id VARCHAR(36) REFERENCES repertoire_items(id) ON DELETE CASCADE,
            signal_type VARCHAR(32) NOT NULL DEFAULT 'interaction',
            weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            occurred_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (id, occurred_at)
        ) PARTITION BY RANGE (occurred_at)
        """
    )

    # Near-term bounded partitions plus a DEFAULT partition for out-of-band timestamps.
    op.execute(
        """
        CREATE TABLE recommendation_signals_2026_h1
        PARTITION OF recommendation_signals
        FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-07-01 00:00:00+00')
        """
    )
    op.execute(
        """
        CREATE TABLE recommendation_signals_2026_h2
        PARTITION OF recommendation_signals
        FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2027-01-01 00:00:00+00')
        """
    )
    op.execute("CREATE TABLE recommendation_signals_default PARTITION OF recommendation_signals DEFAULT")

    op.execute(
        """
        INSERT INTO recommendation_signals (
            id,
            organization_id,
            program_id,
            event_id,
            store_id,
            surface,
            user_id,
            directory_entry_id,
            repertoire_item_id,
            signal_type,
            weight,
            occurred_at,
            created_at
        )
        SELECT
            id,
            organization_id,
            program_id,
            event_id,
            store_id,
            surface,
            NULL,
            directory_entry_id,
            repertoire_item_id,
            signal_type,
            weight,
            occurred_at,
            created_at
        FROM recommendation_signals_unpartitioned
        """
    )

    op.drop_table("recommendation_signals_unpartitioned")
    _create_recommendation_signal_indexes()


def _downgrade_postgresql_recommendation_signals() -> None:
    op.execute("ALTER TABLE recommendation_signals RENAME TO recommendation_signals_partitioned")

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

    op.execute(
        """
        INSERT INTO recommendation_signals (
            id,
            organization_id,
            program_id,
            event_id,
            store_id,
            surface,
            directory_entry_id,
            repertoire_item_id,
            signal_type,
            weight,
            occurred_at,
            created_at
        )
        SELECT
            id,
            organization_id,
            program_id,
            event_id,
            store_id,
            surface,
            directory_entry_id,
            repertoire_item_id,
            signal_type,
            weight,
            occurred_at,
            created_at
        FROM recommendation_signals_partitioned
        """
    )

    op.execute("DROP TABLE recommendation_signals_partitioned CASCADE")

    # Restore original single-column index shape from the prior migration series.
    op.create_index("ix_recommendation_signals_organization_id", "recommendation_signals", ["organization_id"])
    op.create_index("ix_recommendation_signals_program_id", "recommendation_signals", ["program_id"])
    op.create_index("ix_recommendation_signals_event_id", "recommendation_signals", ["event_id"])
    op.create_index("ix_recommendation_signals_store_id", "recommendation_signals", ["store_id"])
    op.create_index("ix_recommendation_signals_surface", "recommendation_signals", ["surface"])
    op.create_index("ix_recommendation_signals_directory_entry_id", "recommendation_signals", ["directory_entry_id"])
    op.create_index("ix_recommendation_signals_repertoire_item_id", "recommendation_signals", ["repertoire_item_id"])
    op.create_index("ix_recommendation_signals_occurred_at", "recommendation_signals", ["occurred_at"])


def _upgrade_postgresql_json_documents() -> None:
    for table_name, column_name in JSON_DOCUMENT_COLUMNS:
        op.execute(
            f"ALTER TABLE {table_name} "
            f"ALTER COLUMN {column_name} TYPE JSONB "
            f"USING {column_name}::jsonb"
        )


def _downgrade_postgresql_json_documents() -> None:
    for table_name, column_name in JSON_DOCUMENT_COLUMNS:
        op.execute(
            f"ALTER TABLE {table_name} "
            f"ALTER COLUMN {column_name} TYPE JSON "
            f"USING {column_name}::json"
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _upgrade_postgresql_recommendation_signals()
        _upgrade_postgresql_json_documents()
        return

    with op.batch_alter_table("recommendation_signals") as batch:
        batch.add_column(sa.Column("user_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_recommendation_signals_user_id", "users", ["user_id"], ["id"])

    _create_recommendation_signal_indexes()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _downgrade_postgresql_recommendation_signals()
        _downgrade_postgresql_json_documents()
        return

    _drop_recommendation_signal_indexes()
    with op.batch_alter_table("recommendation_signals") as batch:
        batch.drop_constraint("fk_recommendation_signals_user_id", type_="foreignkey")
        batch.drop_column("user_id")
