from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.dialects.postgresql import JSONB

from app.db.models import (
    AuditEvent,
    BackupRun,
    ExportRun,
    ImportBatch,
    ImportMergeAction,
    ImportNormalizedRow,
    RecommendationSignal,
    RecoveryDrillRun,
)


def _assert_json_document_type(column: sa.Column) -> None:
    postgres_impl = column.type.dialect_impl(postgresql.dialect())
    sqlite_impl = column.type.dialect_impl(sqlite.dialect())

    assert isinstance(postgres_impl, JSONB)
    assert isinstance(sqlite_impl, sa.JSON)


def test_flexible_document_fields_use_jsonb_on_postgresql_and_json_on_sqlite() -> None:
    json_columns = [
        AuditEvent.__table__.c.details_json,
        ImportBatch.__table__.c.validation_issues_json,
        ImportNormalizedRow.__table__.c.raw_row_json,
        ImportNormalizedRow.__table__.c.normalized_json,
        ImportNormalizedRow.__table__.c.issues_json,
        ImportMergeAction.__table__.c.before_snapshot_json,
        ImportMergeAction.__table__.c.applied_changes_json,
        ExportRun.__table__.c.filters_json,
        BackupRun.__table__.c.verification_json,
        RecoveryDrillRun.__table__.c.evidence_json,
    ]

    for column in json_columns:
        _assert_json_document_type(column)


def test_recommendation_signals_include_optional_user_dimension() -> None:
    user_id = RecommendationSignal.__table__.c.user_id
    assert user_id.nullable is True
    assert user_id.index is True
    assert any(fk.column.table.name == "users" and fk.column.name == "id" for fk in user_id.foreign_keys)
