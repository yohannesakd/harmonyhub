"""add uploads imports merge and account freeze controls

Revision ID: 20260328_0008
Revises: 20260328_0007
Create Date: 2026-03-28 21:05:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260328_0008"
down_revision: Union[str, None] = "20260328_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("freeze_reason", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("frozen_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("unfrozen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("unfrozen_by_user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_users_frozen_by_user_id", "users", "users", ["frozen_by_user_id"], ["id"])
    op.create_foreign_key("fk_users_unfrozen_by_user_id", "users", "users", ["unfrozen_by_user_id"], ["id"])

    op.create_table(
        "uploaded_assets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("extension", sa.String(length=16), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("detected_type", sa.String(length=24), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("import_kind", sa.String(length=32), nullable=True),
        sa.Column("raw_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_uploaded_assets_organization_id", "uploaded_assets", ["organization_id"])
    op.create_index("ix_uploaded_assets_program_id", "uploaded_assets", ["program_id"])
    op.create_index("ix_uploaded_assets_event_id", "uploaded_assets", ["event_id"])
    op.create_index("ix_uploaded_assets_store_id", "uploaded_assets", ["store_id"])
    op.create_index("ix_uploaded_assets_uploaded_by_user_id", "uploaded_assets", ["uploaded_by_user_id"])
    op.create_index("ix_uploaded_assets_sha256", "uploaded_assets", ["sha256"])

    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("uploaded_asset_id", sa.String(length=36), sa.ForeignKey("uploaded_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("issue_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("validation_issues_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("uploaded_asset_id", name="uq_import_batches_uploaded_asset"),
    )
    op.create_index("ix_import_batches_organization_id", "import_batches", ["organization_id"])
    op.create_index("ix_import_batches_program_id", "import_batches", ["program_id"])
    op.create_index("ix_import_batches_event_id", "import_batches", ["event_id"])
    op.create_index("ix_import_batches_store_id", "import_batches", ["store_id"])
    op.create_index("ix_import_batches_uploaded_asset_id", "import_batches", ["uploaded_asset_id"])
    op.create_index("ix_import_batches_status", "import_batches", ["status"])

    op.create_table(
        "import_normalized_rows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_row_json", sa.JSON(), nullable=False),
        sa.Column("normalized_json", sa.JSON(), nullable=True),
        sa.Column("issues_json", sa.JSON(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("effect_target_type", sa.String(length=64), nullable=True),
        sa.Column("effect_target_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "row_number", name="uq_import_normalized_rows_batch_row"),
    )
    op.create_index("ix_import_normalized_rows_batch_id", "import_normalized_rows", ["batch_id"])
    op.create_index("ix_import_normalized_rows_processing_status", "import_normalized_rows", ["processing_status"])

    op.create_table(
        "import_merge_actions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("program_id", sa.String(length=36), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("event_id", sa.String(length=36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("duplicate_candidate_id", sa.String(length=36), nullable=False),
        sa.Column("target_directory_entry_id", sa.String(length=36), sa.ForeignKey("directory_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("merged_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("before_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("applied_changes_json", sa.JSON(), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("undone_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("undo_reason", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_import_merge_actions_organization_id", "import_merge_actions", ["organization_id"])
    op.create_index("ix_import_merge_actions_program_id", "import_merge_actions", ["program_id"])
    op.create_index("ix_import_merge_actions_event_id", "import_merge_actions", ["event_id"])
    op.create_index("ix_import_merge_actions_store_id", "import_merge_actions", ["store_id"])
    op.create_index("ix_import_merge_actions_duplicate_candidate_id", "import_merge_actions", ["duplicate_candidate_id"])
    op.create_index("ix_import_merge_actions_target_directory_entry_id", "import_merge_actions", ["target_directory_entry_id"])

    op.create_table(
        "import_duplicate_candidates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("normalized_row_id", sa.String(length=36), sa.ForeignKey("import_normalized_rows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_directory_entry_id", sa.String(length=36), sa.ForeignKey("directory_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("merge_action_id", sa.String(length=36), sa.ForeignKey("import_merge_actions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("normalized_row_id", "target_directory_entry_id", name="uq_import_duplicate_candidates_row_target"),
    )
    op.create_index("ix_import_duplicate_candidates_batch_id", "import_duplicate_candidates", ["batch_id"])
    op.create_index("ix_import_duplicate_candidates_normalized_row_id", "import_duplicate_candidates", ["normalized_row_id"])
    op.create_index("ix_import_duplicate_candidates_target_directory_entry_id", "import_duplicate_candidates", ["target_directory_entry_id"])
    op.create_index("ix_import_duplicate_candidates_status", "import_duplicate_candidates", ["status"])
    op.create_index("ix_import_duplicate_candidates_merge_action_id", "import_duplicate_candidates", ["merge_action_id"])


def downgrade() -> None:
    op.drop_index("ix_import_duplicate_candidates_merge_action_id", table_name="import_duplicate_candidates")
    op.drop_index("ix_import_duplicate_candidates_status", table_name="import_duplicate_candidates")
    op.drop_index("ix_import_duplicate_candidates_target_directory_entry_id", table_name="import_duplicate_candidates")
    op.drop_index("ix_import_duplicate_candidates_normalized_row_id", table_name="import_duplicate_candidates")
    op.drop_index("ix_import_duplicate_candidates_batch_id", table_name="import_duplicate_candidates")
    op.drop_table("import_duplicate_candidates")

    op.drop_index("ix_import_merge_actions_target_directory_entry_id", table_name="import_merge_actions")
    op.drop_index("ix_import_merge_actions_duplicate_candidate_id", table_name="import_merge_actions")
    op.drop_index("ix_import_merge_actions_store_id", table_name="import_merge_actions")
    op.drop_index("ix_import_merge_actions_event_id", table_name="import_merge_actions")
    op.drop_index("ix_import_merge_actions_program_id", table_name="import_merge_actions")
    op.drop_index("ix_import_merge_actions_organization_id", table_name="import_merge_actions")
    op.drop_table("import_merge_actions")

    op.drop_index("ix_import_normalized_rows_processing_status", table_name="import_normalized_rows")
    op.drop_index("ix_import_normalized_rows_batch_id", table_name="import_normalized_rows")
    op.drop_table("import_normalized_rows")

    op.drop_index("ix_import_batches_status", table_name="import_batches")
    op.drop_index("ix_import_batches_uploaded_asset_id", table_name="import_batches")
    op.drop_index("ix_import_batches_store_id", table_name="import_batches")
    op.drop_index("ix_import_batches_event_id", table_name="import_batches")
    op.drop_index("ix_import_batches_program_id", table_name="import_batches")
    op.drop_index("ix_import_batches_organization_id", table_name="import_batches")
    op.drop_table("import_batches")

    op.drop_index("ix_uploaded_assets_sha256", table_name="uploaded_assets")
    op.drop_index("ix_uploaded_assets_uploaded_by_user_id", table_name="uploaded_assets")
    op.drop_index("ix_uploaded_assets_store_id", table_name="uploaded_assets")
    op.drop_index("ix_uploaded_assets_event_id", table_name="uploaded_assets")
    op.drop_index("ix_uploaded_assets_program_id", table_name="uploaded_assets")
    op.drop_index("ix_uploaded_assets_organization_id", table_name="uploaded_assets")
    op.drop_table("uploaded_assets")

    op.drop_constraint("fk_users_unfrozen_by_user_id", "users", type_="foreignkey")
    op.drop_constraint("fk_users_frozen_by_user_id", "users", type_="foreignkey")
    op.drop_column("users", "unfrozen_by_user_id")
    op.drop_column("users", "unfrozen_at")
    op.drop_column("users", "frozen_by_user_id")
    op.drop_column("users", "freeze_reason")
    op.drop_column("users", "frozen_at")
