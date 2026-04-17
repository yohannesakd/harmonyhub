from __future__ import annotations

import base64
import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import and_, func, select, text
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import DateTime as SQLDateTime

from app.core.config import Settings, get_settings
from app.core.field_encryption import decrypt_bytes, encrypt_bytes
from app.core.logging import sanitize_exception_for_log
from app.db.base import Base
from app.db.models import (
    AbacRule,
    AbacSurfaceSetting,
    AddressBookEntry,
    AuditEvent,
    AvailabilityWindow,
    BackupRun,
    DeliveryZone,
    DirectoryEntry,
    DirectoryEntryRepertoireItem,
    DirectoryEntryTag,
    Event,
    ExportRun,
    ImportBatch,
    ImportDuplicateCandidate,
    ImportMergeAction,
    ImportNormalizedRow,
    Membership,
    MenuItem,
    Order,
    OrderItem,
    Organization,
    PairingRule,
    Program,
    RecoveryDrillRun,
    RecommendationConfig,
    RecommendationFeaturedPin,
    RecommendationSignal,
    RepertoireItem,
    RepertoireItemTag,
    SlotCapacity,
    Store,
    Tag,
    UploadedAsset,
    User,
)

BACKUP_FORMAT_VERSION = 2
RESTORE_DB_DIRNAME = "recovery_drill_restores"
BYTES_ENCODING_MARKER = "bytes_b64"


@dataclass
class BackupScope:
    organization_id: str
    program_id: str
    event_id: str
    store_id: str


TABLE_MODEL_MAP = {
    "organizations": Organization,
    "programs": Program,
    "events": Event,
    "stores": Store,
    "users": User,
    "memberships": Membership,
    "abac_surface_settings": AbacSurfaceSetting,
    "abac_rules": AbacRule,
    "tags": Tag,
    "directory_entries": DirectoryEntry,
    "repertoire_items": RepertoireItem,
    "directory_entry_tags": DirectoryEntryTag,
    "repertoire_item_tags": RepertoireItemTag,
    "directory_entry_repertoire_items": DirectoryEntryRepertoireItem,
    "availability_windows": AvailabilityWindow,
    "recommendation_configs": RecommendationConfig,
    "recommendation_signals": RecommendationSignal,
    "recommendation_featured_pins": RecommendationFeaturedPin,
    "pairing_rules": PairingRule,
    "menu_items": MenuItem,
    "address_book_entries": AddressBookEntry,
    "delivery_zones": DeliveryZone,
    "slot_capacities": SlotCapacity,
    "orders": Order,
    "order_items": OrderItem,
    "uploaded_assets": UploadedAsset,
    "import_batches": ImportBatch,
    "import_normalized_rows": ImportNormalizedRow,
    "import_merge_actions": ImportMergeAction,
    "import_duplicate_candidates": ImportDuplicateCandidate,
    "audit_events": AuditEvent,
    "export_runs": ExportRun,
    "backup_runs": BackupRun,
    "recovery_drill_runs": RecoveryDrillRun,
}

RESTORE_TABLE_ORDER = [
    "organizations",
    "programs",
    "events",
    "stores",
    "users",
    "memberships",
    "abac_surface_settings",
    "abac_rules",
    "tags",
    "directory_entries",
    "repertoire_items",
    "directory_entry_tags",
    "repertoire_item_tags",
    "directory_entry_repertoire_items",
    "availability_windows",
    "recommendation_configs",
    "recommendation_signals",
    "recommendation_featured_pins",
    "pairing_rules",
    "menu_items",
    "address_book_entries",
    "delivery_zones",
    "slot_capacities",
    "orders",
    "order_items",
    "uploaded_assets",
    "import_batches",
    "import_normalized_rows",
    "import_merge_actions",
    "import_duplicate_candidates",
    "audit_events",
    "export_runs",
    "backup_runs",
    "recovery_drill_runs",
]

CRITICAL_TENANT_TABLES = [
    "memberships",
    "abac_surface_settings",
    "abac_rules",
    "directory_entries",
    "repertoire_items",
    "menu_items",
    "address_book_entries",
    "delivery_zones",
    "slot_capacities",
    "orders",
    "order_items",
    "import_batches",
    "import_normalized_rows",
    "import_duplicate_candidates",
    "audit_events",
]


def _compute_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _scope_match(model, scope: BackupScope):
    return and_(
        model.organization_id == scope.organization_id,
        model.program_id == scope.program_id,
        model.event_id == scope.event_id,
        model.store_id == scope.store_id,
    )


def _serialize_value(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    if isinstance(value, bytes):
        return {
            "__backup_encoding__": BYTES_ENCODING_MARKER,
            "value": base64.b64encode(value).decode("ascii"),
        }
    if isinstance(value, dict):
        return {key: _serialize_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_serialize_value(child) for child in value]
    return value


def _parse_datetime(value: str) -> datetime:
    raw = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _deserialize_value(value):
    if isinstance(value, dict):
        if value.get("__backup_encoding__") == BYTES_ENCODING_MARKER:
            encoded = value.get("value")
            if not isinstance(encoded, str):
                raise ValueError("Invalid bytes encoding in backup artifact")
            return base64.b64decode(encoded.encode("ascii"))
        return {key: _deserialize_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_deserialize_value(child) for child in value]
    return value


def _serialize_model_rows(rows) -> list[dict]:
    if not rows:
        return []
    model = type(rows[0])
    columns = model.__table__.columns
    serialized: list[dict] = []
    for row in rows:
        payload = {}
        for column in columns:
            payload[column.name] = _serialize_value(getattr(row, column.name))
        serialized.append(payload)
    return serialized


def _decode_row_for_insert(model, row_payload: dict) -> dict:
    decoded: dict = {}
    for column in model.__table__.columns:
        if column.name not in row_payload:
            continue
        value = _deserialize_value(row_payload[column.name])
        if value is not None and isinstance(column.type, SQLDateTime):
            if not isinstance(value, str):
                raise ValueError(f"Invalid datetime value for {model.__tablename__}.{column.name}")
            decoded[column.name] = _parse_datetime(value)
        else:
            decoded[column.name] = value
    return decoded


def _backup_payload_for_scope(db: Session, scope: BackupScope) -> dict:
    organization = db.get(Organization, scope.organization_id)
    program = db.get(Program, scope.program_id)
    event = db.get(Event, scope.event_id)
    store = db.get(Store, scope.store_id)
    if not (organization and program and event and store):
        raise ValueError("Backup scope hierarchy is incomplete")

    memberships = db.scalars(select(Membership).where(_scope_match(Membership, scope))).all()
    users_by_id = {row.user_id for row in memberships}

    abac_surface_settings = db.scalars(
        select(AbacSurfaceSetting).where(AbacSurfaceSetting.organization_id == scope.organization_id)
    ).all()
    abac_rules = db.scalars(select(AbacRule).where(AbacRule.organization_id == scope.organization_id)).all()

    directory_entries = db.scalars(select(DirectoryEntry).where(_scope_match(DirectoryEntry, scope))).all()
    directory_entry_ids = {row.id for row in directory_entries}

    repertoire_items = db.scalars(select(RepertoireItem).where(_scope_match(RepertoireItem, scope))).all()
    repertoire_item_ids = {row.id for row in repertoire_items}

    tags = db.scalars(select(Tag).where(Tag.organization_id == scope.organization_id)).all()

    directory_entry_tags = (
        db.scalars(select(DirectoryEntryTag).where(DirectoryEntryTag.directory_entry_id.in_(directory_entry_ids))).all()
        if directory_entry_ids
        else []
    )
    repertoire_item_tags = (
        db.scalars(select(RepertoireItemTag).where(RepertoireItemTag.repertoire_item_id.in_(repertoire_item_ids))).all()
        if repertoire_item_ids
        else []
    )
    directory_repertoire_links = (
        db.scalars(
            select(DirectoryEntryRepertoireItem).where(
                DirectoryEntryRepertoireItem.directory_entry_id.in_(directory_entry_ids),
                DirectoryEntryRepertoireItem.repertoire_item_id.in_(repertoire_item_ids),
            )
        ).all()
        if directory_entry_ids and repertoire_item_ids
        else []
    )
    availability_windows = (
        db.scalars(select(AvailabilityWindow).where(AvailabilityWindow.directory_entry_id.in_(directory_entry_ids))).all()
        if directory_entry_ids
        else []
    )

    recommendation_configs = db.scalars(
        select(RecommendationConfig).where(
            RecommendationConfig.organization_id == scope.organization_id,
            (RecommendationConfig.program_id.is_(None) | (RecommendationConfig.program_id == scope.program_id)),
            (RecommendationConfig.event_id.is_(None) | (RecommendationConfig.event_id == scope.event_id)),
            (RecommendationConfig.store_id.is_(None) | (RecommendationConfig.store_id == scope.store_id)),
        )
    ).all()
    recommendation_signals = db.scalars(select(RecommendationSignal).where(_scope_match(RecommendationSignal, scope))).all()
    recommendation_featured_pins = db.scalars(
        select(RecommendationFeaturedPin).where(_scope_match(RecommendationFeaturedPin, scope))
    ).all()
    pairing_rules = db.scalars(select(PairingRule).where(_scope_match(PairingRule, scope))).all()

    menu_items = db.scalars(select(MenuItem).where(_scope_match(MenuItem, scope))).all()
    delivery_zones = db.scalars(select(DeliveryZone).where(_scope_match(DeliveryZone, scope))).all()
    slot_capacities = db.scalars(select(SlotCapacity).where(_scope_match(SlotCapacity, scope))).all()

    orders = db.scalars(select(Order).where(_scope_match(Order, scope))).all()
    order_ids = {row.id for row in orders}
    users_by_id.update(row.user_id for row in orders)

    order_items = (
        db.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids))).all()
        if order_ids
        else []
    )

    addresses = (
        db.scalars(
            select(AddressBookEntry).where(
                AddressBookEntry.organization_id == scope.organization_id,
                AddressBookEntry.user_id.in_(users_by_id),
            )
        ).all()
        if users_by_id
        else []
    )

    uploaded_assets = db.scalars(select(UploadedAsset).where(_scope_match(UploadedAsset, scope))).all()
    asset_ids = {row.id for row in uploaded_assets}
    users_by_id.update(row.uploaded_by_user_id for row in uploaded_assets)

    import_batches = db.scalars(select(ImportBatch).where(_scope_match(ImportBatch, scope))).all()
    batch_ids = {row.id for row in import_batches}

    import_normalized_rows = (
        db.scalars(select(ImportNormalizedRow).where(ImportNormalizedRow.batch_id.in_(batch_ids))).all()
        if batch_ids
        else []
    )
    import_merge_actions = db.scalars(select(ImportMergeAction).where(_scope_match(ImportMergeAction, scope))).all()
    import_duplicate_candidates = (
        db.scalars(select(ImportDuplicateCandidate).where(ImportDuplicateCandidate.batch_id.in_(batch_ids))).all()
        if batch_ids
        else []
    )

    audit_events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.organization_id == scope.organization_id,
            AuditEvent.program_id == scope.program_id,
            AuditEvent.event_id == scope.event_id,
            AuditEvent.store_id == scope.store_id,
        )
    ).all()
    users_by_id.update(row.actor_user_id for row in audit_events if row.actor_user_id)

    export_runs = db.scalars(select(ExportRun).where(_scope_match(ExportRun, scope))).all()
    users_by_id.update(row.requested_by_user_id for row in export_runs)

    backup_runs = db.scalars(select(BackupRun).where(_scope_match(BackupRun, scope))).all()
    users_by_id.update(row.triggered_by_user_id for row in backup_runs if row.triggered_by_user_id)

    recovery_drill_runs = db.scalars(select(RecoveryDrillRun).where(_scope_match(RecoveryDrillRun, scope))).all()
    users_by_id.update(row.performed_by_user_id for row in recovery_drill_runs)

    users = db.scalars(select(User).where(User.id.in_(users_by_id))).all() if users_by_id else []

    tables = {
        "organizations": _serialize_model_rows([organization]),
        "programs": _serialize_model_rows([program]),
        "events": _serialize_model_rows([event]),
        "stores": _serialize_model_rows([store]),
        "users": _serialize_model_rows(users),
        "memberships": _serialize_model_rows(memberships),
        "abac_surface_settings": _serialize_model_rows(abac_surface_settings),
        "abac_rules": _serialize_model_rows(abac_rules),
        "tags": _serialize_model_rows(tags),
        "directory_entries": _serialize_model_rows(directory_entries),
        "repertoire_items": _serialize_model_rows(repertoire_items),
        "directory_entry_tags": _serialize_model_rows(directory_entry_tags),
        "repertoire_item_tags": _serialize_model_rows(repertoire_item_tags),
        "directory_entry_repertoire_items": _serialize_model_rows(directory_repertoire_links),
        "availability_windows": _serialize_model_rows(availability_windows),
        "recommendation_configs": _serialize_model_rows(recommendation_configs),
        "recommendation_signals": _serialize_model_rows(recommendation_signals),
        "recommendation_featured_pins": _serialize_model_rows(recommendation_featured_pins),
        "pairing_rules": _serialize_model_rows(pairing_rules),
        "menu_items": _serialize_model_rows(menu_items),
        "address_book_entries": _serialize_model_rows(addresses),
        "delivery_zones": _serialize_model_rows(delivery_zones),
        "slot_capacities": _serialize_model_rows(slot_capacities),
        "orders": _serialize_model_rows(orders),
        "order_items": _serialize_model_rows(order_items),
        "uploaded_assets": _serialize_model_rows(uploaded_assets),
        "import_batches": _serialize_model_rows(import_batches),
        "import_normalized_rows": _serialize_model_rows(import_normalized_rows),
        "import_merge_actions": _serialize_model_rows(import_merge_actions),
        "import_duplicate_candidates": _serialize_model_rows(import_duplicate_candidates),
        "audit_events": _serialize_model_rows(audit_events),
        "export_runs": _serialize_model_rows(export_runs),
        "backup_runs": _serialize_model_rows(backup_runs),
        "recovery_drill_runs": _serialize_model_rows(recovery_drill_runs),
    }
    table_counts = {table_name: len(rows) for table_name, rows in tables.items()}

    return {
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "backup_kind": "tenant_logical_full",
        "scope": {
            "organization_id": scope.organization_id,
            "program_id": scope.program_id,
            "event_id": scope.event_id,
            "store_id": scope.store_id,
        },
        "generated_at": datetime.now(UTC).isoformat(),
        "tables": tables,
        "verification": {
            "checksum_algorithm": "sha256",
            "table_counts": table_counts,
            "critical_tenant_tables": CRITICAL_TENANT_TABLES,
        },
    }


def run_backup_for_scope(
    db: Session,
    *,
    scope: BackupScope,
    triggered_by_user_id: str | None,
    trigger_type: str,
    copy_to_offline_medium: bool,
) -> BackupRun:
    settings = get_settings()
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    payload = _backup_payload_for_scope(db, scope)
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    digest = _compute_sha256(payload_bytes)
    encrypted_payload_bytes = encrypt_bytes(payload_bytes)
    encrypted_digest = _compute_sha256(encrypted_payload_bytes)

    filename = (
        f"backup_{scope.organization_id[:8]}_{scope.program_id[:8]}_{scope.event_id[:8]}_{scope.store_id[:8]}_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    file_path = backup_dir / filename
    file_path.write_bytes(encrypted_payload_bytes)

    offline_copy_path: str | None = None
    offline_verified = False
    if copy_to_offline_medium:
        offline_dir = Path(settings.backup_offline_medium_dir)
        offline_dir.mkdir(parents=True, exist_ok=True)
        copied_file_path = offline_dir / filename
        shutil.copyfile(file_path, copied_file_path)
        copied_digest = _compute_sha256(copied_file_path.read_bytes())
        offline_verified = copied_digest == encrypted_digest
        offline_copy_path = str(copied_file_path)

    table_counts = payload["verification"]["table_counts"]
    verification = {
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "backup_kind": payload["backup_kind"],
        "checksum_algorithm": "sha256",
        "table_counts": table_counts,
        "row_counts": table_counts,
        "critical_tenant_tables": CRITICAL_TENANT_TABLES,
        "offline_copy_verified": offline_verified,
    }

    run = BackupRun(
        organization_id=scope.organization_id,
        program_id=scope.program_id,
        event_id=scope.event_id,
        store_id=scope.store_id,
        triggered_by_user_id=triggered_by_user_id,
        trigger_type=trigger_type,
        status="completed",
        file_path=str(file_path),
        file_size_bytes=len(encrypted_payload_bytes),
        sha256=digest,
        offline_copy_path=offline_copy_path,
        offline_copy_verified=offline_verified,
        verification_json=verification,
        completed_at=datetime.now(UTC),
    )
    db.add(run)
    db.flush()
    return run


def _nightly_scope_query():
    return select(
        Membership.organization_id,
        Membership.program_id,
        Membership.event_id,
        Membership.store_id,
    ).distinct()


def run_nightly_backups_if_due(db: Session, settings: Settings | None = None) -> int:
    cfg = settings or get_settings()
    if not cfg.backup_nightly_enabled:
        return 0

    now = datetime.now(UTC)
    if now.hour < cfg.backup_nightly_hour_utc:
        return 0

    created = 0
    rows = db.execute(_nightly_scope_query()).all()
    for organization_id, program_id, event_id, store_id in rows:
        today = now.date()
        existing = db.scalar(
            select(BackupRun)
            .where(
                BackupRun.organization_id == organization_id,
                BackupRun.program_id == program_id,
                BackupRun.event_id == event_id,
                BackupRun.store_id == store_id,
                BackupRun.trigger_type == "nightly",
                BackupRun.status == "completed",
            )
            .order_by(BackupRun.created_at.desc())
        )
        if existing and existing.created_at.date() == today:
            continue

        run_backup_for_scope(
            db,
            scope=BackupScope(
                organization_id=organization_id,
                program_id=program_id,
                event_id=event_id,
                store_id=store_id,
            ),
            triggered_by_user_id=None,
            trigger_type="nightly",
            copy_to_offline_medium=True,
        )
        created += 1

    if created:
        db.commit()
    return created


def _load_and_verify_backup_payload(backup_run: BackupRun) -> dict:
    artifact_path = Path(backup_run.file_path)
    if not artifact_path.exists():
        raise ValueError("Backup artifact file does not exist")

    encrypted_payload = artifact_path.read_bytes()
    try:
        bytes_payload = decrypt_bytes(encrypted_payload)
    except ValueError as exc:
        raise ValueError("Backup artifact decryption failed") from exc

    digest = _compute_sha256(bytes_payload)
    if digest != backup_run.sha256:
        raise ValueError("Backup checksum verification failed")

    payload = json.loads(bytes_payload)
    if payload.get("backup_format_version") != BACKUP_FORMAT_VERSION:
        raise ValueError("Unsupported backup format version")
    if payload.get("backup_kind") != "tenant_logical_full":
        raise ValueError("Unsupported backup kind")
    if "tables" not in payload or not isinstance(payload["tables"], dict):
        raise ValueError("Backup payload missing table data")
    return payload


def _restore_rows_to_connection(connection: Connection, payload: dict) -> None:
    for table_name in RESTORE_TABLE_ORDER:
        model = TABLE_MODEL_MAP[table_name]
        rows = payload["tables"].get(table_name, [])
        if not rows:
            continue
        decoded_rows = [_decode_row_for_insert(model, row) for row in rows]
        connection.execute(model.__table__.insert(), decoded_rows)


def _count_rows_from_connection(connection: Connection) -> dict[str, int]:
    restored_counts: dict[str, int] = {}
    for table_name in RESTORE_TABLE_ORDER:
        model = TABLE_MODEL_MAP[table_name]
        count = connection.execute(select(func.count()).select_from(model.__table__)).scalar_one()
        restored_counts[table_name] = int(count)
    return restored_counts


def _counts_match_expected(restored_counts: dict[str, int], expected_counts: dict[str, int]) -> bool:
    return all(restored_counts.get(name, 0) == int(expected_counts.get(name, 0)) for name in RESTORE_TABLE_ORDER)


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _restore_backup_payload_to_isolated_sqlite_database(payload: dict, *, backup_run_id: str, settings: Settings) -> dict:
    restore_dir = Path(settings.backup_dir) / RESTORE_DB_DIRNAME
    restore_dir.mkdir(parents=True, exist_ok=True)
    restore_filename = f"restore_{backup_run_id[:8]}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}.sqlite"
    restore_path = restore_dir / restore_filename
    if restore_path.exists():
        restore_path.unlink()

    restore_engine = create_engine(f"sqlite+pysqlite:///{restore_path}")
    Base.metadata.create_all(restore_engine)

    with restore_engine.begin() as connection:
        _restore_rows_to_connection(connection, payload)

    with restore_engine.connect() as connection:
        restored_counts = _count_rows_from_connection(connection)

    expected_counts = payload["verification"]["table_counts"]
    counts_match = _counts_match_expected(restored_counts, expected_counts)

    return {
        "status": "completed" if counts_match else "failed",
        "restore_target": "isolated_sqlite_database",
        "restore_database_path": str(restore_path),
        "table_counts_match": counts_match,
        "restored_table_counts": restored_counts,
        "expected_table_counts": expected_counts,
    }


def _restore_backup_payload_to_isolated_postgres_schema(payload: dict, *, backup_run_id: str, settings: Settings) -> dict:
    restore_schema = (
        f"drill_restore_{backup_run_id.replace('-', '')[:8]}_"
        f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    restore_engine = create_engine(settings.database_url, pool_pre_ping=True)

    with restore_engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(restore_schema)}"))
        connection.execute(text(f"SET search_path TO {_quote_ident(restore_schema)}"))
        Base.metadata.create_all(connection)
        _restore_rows_to_connection(connection, payload)

    with restore_engine.begin() as connection:
        connection.execute(text(f"SET search_path TO {_quote_ident(restore_schema)}"))
        restored_counts = _count_rows_from_connection(connection)

    expected_counts = payload["verification"]["table_counts"]
    counts_match = _counts_match_expected(restored_counts, expected_counts)
    parsed_url = make_url(settings.database_url)

    return {
        "status": "completed" if counts_match else "failed",
        "restore_target": "isolated_postgres_schema",
        "restore_schema": restore_schema,
        "restore_database": parsed_url.database,
        "table_counts_match": counts_match,
        "restored_table_counts": restored_counts,
        "expected_table_counts": expected_counts,
    }


def run_recovery_drill_restore(backup_run: BackupRun, settings: Settings | None = None) -> dict:
    cfg = settings or get_settings()
    payload = _load_and_verify_backup_payload(backup_run)
    dialect_name = make_url(cfg.database_url).get_backend_name()

    if dialect_name.startswith("postgres"):
        restore_summary = _restore_backup_payload_to_isolated_postgres_schema(
            payload,
            backup_run_id=backup_run.id,
            settings=cfg,
        )
    else:
        restore_summary = _restore_backup_payload_to_isolated_sqlite_database(
            payload,
            backup_run_id=backup_run.id,
            settings=cfg,
        )

    restore_summary["restore_dialect"] = dialect_name
    restore_summary["backup_sha256_verified"] = True
    restore_summary["backup_file_path"] = backup_run.file_path
    restore_summary["backup_run_id"] = backup_run.id
    return restore_summary


def _finalize_recovery_drill_status(*, declared_status: str, restore_status: str) -> str:
    if restore_status != "completed":
        return "failed"
    if declared_status == "failed":
        return "failed"
    if declared_status == "inconclusive":
        return "inconclusive"
    return "passed"


def _restore_failure_reason_for_notes(error_value: object) -> str:
    if isinstance(error_value, str) and error_value.strip():
        return error_value.strip()
    if isinstance(error_value, dict):
        message = error_value.get("exception_message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        error_type = error_value.get("exception_type")
        if isinstance(error_type, str) and error_type.strip():
            return error_type.strip()
    return "restore verification failed"


def create_recovery_drill(
    db: Session,
    *,
    scope: BackupScope,
    backup_run: BackupRun,
    performed_by_user_id: str,
    scenario: str,
    declared_status: str,
    evidence_json: dict | None,
    notes: str | None,
) -> RecoveryDrillRun:
    restore_details: dict
    try:
        restore_details = run_recovery_drill_restore(backup_run)
    except Exception as exc:  # noqa: BLE001
        restore_details = {
            "status": "failed",
            "backup_run_id": backup_run.id,
            "backup_file_path": backup_run.file_path,
            "backup_sha256_verified": False,
            "error": sanitize_exception_for_log(exc),
        }

    merged_evidence = {
        **(evidence_json or {}),
        "restore": restore_details,
    }
    final_status = _finalize_recovery_drill_status(
        declared_status=declared_status,
        restore_status=str(restore_details.get("status", "failed")),
    )

    final_notes = notes
    if restore_details.get("status") != "completed":
        reason = _restore_failure_reason_for_notes(restore_details.get("error"))
        final_notes = (f"{notes} | " if notes else "") + f"Restore drill failed: {reason}"

    drill = RecoveryDrillRun(
        organization_id=scope.organization_id,
        program_id=scope.program_id,
        event_id=scope.event_id,
        store_id=scope.store_id,
        backup_run_id=backup_run.id,
        performed_by_user_id=performed_by_user_id,
        scenario=scenario,
        status=final_status,
        evidence_json=merged_evidence,
        notes=final_notes,
        performed_at=datetime.now(UTC),
    )
    db.add(drill)
    db.flush()
    return drill
