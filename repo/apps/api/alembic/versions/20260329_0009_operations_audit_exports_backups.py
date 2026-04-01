"""add operations exports backups and recovery drill tables

Revision ID: 20260329_0009
Revises: 20260328_0008
Create Date: 2026-03-29 20:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260329_0009"
down_revision: Union[str, None] = "20260328_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "export_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("export_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("include_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("filters_json", sa.JSON(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_export_runs_organization_id", "export_runs", ["organization_id"])
    op.create_index("ix_export_runs_program_id", "export_runs", ["program_id"])
    op.create_index("ix_export_runs_event_id", "export_runs", ["event_id"])
    op.create_index("ix_export_runs_store_id", "export_runs", ["store_id"])
    op.create_index("ix_export_runs_requested_by_user_id", "export_runs", ["requested_by_user_id"])
    op.create_index("ix_export_runs_export_type", "export_runs", ["export_type"])
    op.create_index("ix_export_runs_status", "export_runs", ["status"])
    op.create_index("ix_export_runs_created_at", "export_runs", ["created_at"])

    op.create_table(
        "backup_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("triggered_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("offline_copy_path", sa.String(length=512), nullable=True),
        sa.Column("offline_copy_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verification_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_backup_runs_organization_id", "backup_runs", ["organization_id"])
    op.create_index("ix_backup_runs_program_id", "backup_runs", ["program_id"])
    op.create_index("ix_backup_runs_event_id", "backup_runs", ["event_id"])
    op.create_index("ix_backup_runs_store_id", "backup_runs", ["store_id"])
    op.create_index("ix_backup_runs_triggered_by_user_id", "backup_runs", ["triggered_by_user_id"])
    op.create_index("ix_backup_runs_trigger_type", "backup_runs", ["trigger_type"])
    op.create_index("ix_backup_runs_status", "backup_runs", ["status"])
    op.create_index("ix_backup_runs_created_at", "backup_runs", ["created_at"])

    op.create_table(
        "recovery_drill_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("backup_run_id", sa.String(length=36), sa.ForeignKey("backup_runs.id"), nullable=True),
        sa.Column("performed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scenario", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recovery_drill_runs_organization_id", "recovery_drill_runs", ["organization_id"])
    op.create_index("ix_recovery_drill_runs_program_id", "recovery_drill_runs", ["program_id"])
    op.create_index("ix_recovery_drill_runs_event_id", "recovery_drill_runs", ["event_id"])
    op.create_index("ix_recovery_drill_runs_store_id", "recovery_drill_runs", ["store_id"])
    op.create_index("ix_recovery_drill_runs_backup_run_id", "recovery_drill_runs", ["backup_run_id"])
    op.create_index("ix_recovery_drill_runs_performed_by_user_id", "recovery_drill_runs", ["performed_by_user_id"])
    op.create_index("ix_recovery_drill_runs_status", "recovery_drill_runs", ["status"])
    op.create_index("ix_recovery_drill_runs_performed_at", "recovery_drill_runs", ["performed_at"])


def downgrade() -> None:
    op.drop_index("ix_recovery_drill_runs_performed_at", table_name="recovery_drill_runs")
    op.drop_index("ix_recovery_drill_runs_status", table_name="recovery_drill_runs")
    op.drop_index("ix_recovery_drill_runs_performed_by_user_id", table_name="recovery_drill_runs")
    op.drop_index("ix_recovery_drill_runs_backup_run_id", table_name="recovery_drill_runs")
    op.drop_index("ix_recovery_drill_runs_store_id", table_name="recovery_drill_runs")
    op.drop_index("ix_recovery_drill_runs_event_id", table_name="recovery_drill_runs")
    op.drop_index("ix_recovery_drill_runs_program_id", table_name="recovery_drill_runs")
    op.drop_index("ix_recovery_drill_runs_organization_id", table_name="recovery_drill_runs")
    op.drop_table("recovery_drill_runs")

    op.drop_index("ix_backup_runs_created_at", table_name="backup_runs")
    op.drop_index("ix_backup_runs_status", table_name="backup_runs")
    op.drop_index("ix_backup_runs_trigger_type", table_name="backup_runs")
    op.drop_index("ix_backup_runs_triggered_by_user_id", table_name="backup_runs")
    op.drop_index("ix_backup_runs_store_id", table_name="backup_runs")
    op.drop_index("ix_backup_runs_event_id", table_name="backup_runs")
    op.drop_index("ix_backup_runs_program_id", table_name="backup_runs")
    op.drop_index("ix_backup_runs_organization_id", table_name="backup_runs")
    op.drop_table("backup_runs")

    op.drop_index("ix_export_runs_created_at", table_name="export_runs")
    op.drop_index("ix_export_runs_status", table_name="export_runs")
    op.drop_index("ix_export_runs_export_type", table_name="export_runs")
    op.drop_index("ix_export_runs_requested_by_user_id", table_name="export_runs")
    op.drop_index("ix_export_runs_store_id", table_name="export_runs")
    op.drop_index("ix_export_runs_event_id", table_name="export_runs")
    op.drop_index("ix_export_runs_program_id", table_name="export_runs")
    op.drop_index("ix_export_runs_organization_id", table_name="export_runs")
    op.drop_table("export_runs")
