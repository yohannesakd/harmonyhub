from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import (
    DirectoryEntry,
    DirectoryEntryRepertoireItem,
    DirectoryEntryTag,
    Membership,
    PairingRule,
    RecommendationConfig,
    RecommendationFeaturedPin,
    RecommendationSignal,
    RepertoireItem,
    RepertoireItemTag,
    Tag,
)
from app.schemas.recommendations import RecommendationEnabledModes, RecommendationWeights, ScopeType


@dataclass
class EffectiveRecommendationConfig:
    scope: ScopeType
    inherited_from_scope: ScopeType | None
    config: RecommendationConfig | None
    enabled_modes: RecommendationEnabledModes
    weights: RecommendationWeights
    pins_enabled: bool
    max_pins: int
    pin_ttl_hours: int | None
    enforce_pairing_rules: bool
    allow_staff_event_store_manage: bool


def normalize_weights(weights: RecommendationWeights) -> RecommendationWeights:
    total = weights.popularity_30d + weights.recent_activity_72h + weights.tag_match
    if total <= 0:
        return RecommendationWeights(popularity_30d=0.5, recent_activity_72h=0.3, tag_match=0.2)
    return RecommendationWeights(
        popularity_30d=weights.popularity_30d / total,
        recent_activity_72h=weights.recent_activity_72h / total,
        tag_match=weights.tag_match / total,
    )


def _scope_where_clause(scope: ScopeType, membership: Membership):
    if scope == "organization":
        return (
            RecommendationConfig.organization_id == membership.organization_id,
            RecommendationConfig.program_id.is_(None),
            RecommendationConfig.event_id.is_(None),
            RecommendationConfig.store_id.is_(None),
        )

    if scope == "program":
        return (
            RecommendationConfig.organization_id == membership.organization_id,
            RecommendationConfig.program_id == membership.program_id,
            RecommendationConfig.event_id.is_(None),
            RecommendationConfig.store_id.is_(None),
        )

    return (
        RecommendationConfig.organization_id == membership.organization_id,
        RecommendationConfig.program_id == membership.program_id,
        RecommendationConfig.event_id == membership.event_id,
        RecommendationConfig.store_id == membership.store_id,
    )


def get_exact_config_for_scope(db: Session, membership: Membership, scope: ScopeType) -> RecommendationConfig | None:
    return db.scalar(select(RecommendationConfig).where(*_scope_where_clause(scope, membership)))


def _default_effective(scope: ScopeType, inherited_from_scope: ScopeType | None = None) -> EffectiveRecommendationConfig:
    default_weights = RecommendationWeights(popularity_30d=0.5, recent_activity_72h=0.3, tag_match=0.2)
    return EffectiveRecommendationConfig(
        scope=scope,
        inherited_from_scope=inherited_from_scope,
        config=None,
        enabled_modes=RecommendationEnabledModes(popularity_30d=True, recent_activity_72h=True, tag_match=True),
        weights=default_weights,
        pins_enabled=True,
        max_pins=20,
        pin_ttl_hours=None,
        enforce_pairing_rules=True,
        allow_staff_event_store_manage=False,
    )


def _to_effective(scope: ScopeType, config: RecommendationConfig, inherited_from_scope: ScopeType | None = None):
    return EffectiveRecommendationConfig(
        scope=scope,
        inherited_from_scope=inherited_from_scope,
        config=config,
        enabled_modes=RecommendationEnabledModes(
            popularity_30d=config.enabled_popularity_30d,
            recent_activity_72h=config.enabled_recent_activity_72h,
            tag_match=config.enabled_tag_match,
        ),
        weights=normalize_weights(
            RecommendationWeights(
                popularity_30d=config.weight_popularity_30d,
                recent_activity_72h=config.weight_recent_activity_72h,
                tag_match=config.weight_tag_match,
            )
        ),
        pins_enabled=config.pins_enabled,
        max_pins=config.max_pins,
        pin_ttl_hours=config.pin_ttl_hours,
        enforce_pairing_rules=config.enforce_pairing_rules,
        allow_staff_event_store_manage=config.allow_staff_event_store_manage,
    )


def resolve_effective_config(db: Session, membership: Membership) -> EffectiveRecommendationConfig:
    event_store = get_exact_config_for_scope(db, membership, "event_store")
    if event_store:
        return _to_effective("event_store", event_store)

    program = get_exact_config_for_scope(db, membership, "program")
    if program:
        return _to_effective("program", program)

    organization = get_exact_config_for_scope(db, membership, "organization")
    if organization:
        return _to_effective("organization", organization)

    return _default_effective("organization")


def resolve_config_for_requested_scope(db: Session, membership: Membership, scope: ScopeType) -> EffectiveRecommendationConfig:
    exact = get_exact_config_for_scope(db, membership, scope)
    if exact:
        return _to_effective(scope, exact)

    if scope == "organization":
        return _default_effective("organization")

    if scope == "program":
        org = get_exact_config_for_scope(db, membership, "organization")
        if org:
            return _to_effective("program", org, inherited_from_scope="organization")
        return _default_effective("program", inherited_from_scope="organization")

    # event_store scope fallback chain: program -> organization -> default
    program = get_exact_config_for_scope(db, membership, "program")
    if program:
        return _to_effective("event_store", program, inherited_from_scope="program")
    org = get_exact_config_for_scope(db, membership, "organization")
    if org:
        return _to_effective("event_store", org, inherited_from_scope="organization")
    return _default_effective("event_store", inherited_from_scope="organization")


def staff_can_manage_event_store(db: Session, membership: Membership) -> bool:
    program = get_exact_config_for_scope(db, membership, "program")
    if program:
        return program.allow_staff_event_store_manage
    org = get_exact_config_for_scope(db, membership, "organization")
    if org:
        return org.allow_staff_event_store_manage
    return False


def assert_config_scope_permission(db: Session, membership: Membership, scope: ScopeType) -> None:
    if membership.role == "administrator":
        return

    if membership.role != "staff":
        raise AppError(code="FORBIDDEN", message="Only staff/admin can manage recommendation settings", status_code=403)

    if scope != "event_store":
        raise AppError(code="FORBIDDEN", message="Staff can only manage event/store recommendation settings", status_code=403)

    if not staff_can_manage_event_store(db, membership):
        raise AppError(code="FORBIDDEN", message="Staff delegation for event/store recommendation settings is disabled", status_code=403)


def _scope_filter_for_entries(membership: Membership):
    return (
        DirectoryEntry.organization_id == membership.organization_id,
        DirectoryEntry.program_id == membership.program_id,
        DirectoryEntry.event_id == membership.event_id,
        DirectoryEntry.store_id == membership.store_id,
    )


def _scope_filter_for_repertoire(membership: Membership):
    return (
        RepertoireItem.organization_id == membership.organization_id,
        RepertoireItem.program_id == membership.program_id,
        RepertoireItem.event_id == membership.event_id,
        RepertoireItem.store_id == membership.store_id,
    )


def get_directory_signal_scores(db: Session, membership: Membership, directory_entry_ids: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    if not directory_entry_ids:
        return {}, {}

    now = datetime.now(UTC)
    cutoff_30d = now - timedelta(days=30)
    cutoff_72h = now - timedelta(hours=72)

    popularity_rows = db.execute(
        select(RecommendationSignal.directory_entry_id, func.sum(RecommendationSignal.weight))
        .where(
            RecommendationSignal.surface == "directory",
            RecommendationSignal.organization_id == membership.organization_id,
            RecommendationSignal.program_id == membership.program_id,
            RecommendationSignal.event_id == membership.event_id,
            RecommendationSignal.store_id == membership.store_id,
            RecommendationSignal.directory_entry_id.in_(directory_entry_ids),
            RecommendationSignal.occurred_at >= cutoff_30d,
        )
        .group_by(RecommendationSignal.directory_entry_id)
    ).all()

    recent_rows = db.execute(
        select(RecommendationSignal.directory_entry_id, func.sum(RecommendationSignal.weight))
        .where(
            RecommendationSignal.surface == "directory",
            RecommendationSignal.organization_id == membership.organization_id,
            RecommendationSignal.program_id == membership.program_id,
            RecommendationSignal.event_id == membership.event_id,
            RecommendationSignal.store_id == membership.store_id,
            RecommendationSignal.directory_entry_id.in_(directory_entry_ids),
            RecommendationSignal.occurred_at >= cutoff_72h,
        )
        .group_by(RecommendationSignal.directory_entry_id)
    ).all()

    popularity_map = {entry_id: float(total or 0) for entry_id, total in popularity_rows if entry_id}
    recent_map = {entry_id: float(total or 0) for entry_id, total in recent_rows if entry_id}
    return popularity_map, recent_map


def get_repertoire_signal_scores(
    db: Session, membership: Membership, repertoire_item_ids: list[str]
) -> tuple[dict[str, float], dict[str, float]]:
    if not repertoire_item_ids:
        return {}, {}

    now = datetime.now(UTC)
    cutoff_30d = now - timedelta(days=30)
    cutoff_72h = now - timedelta(hours=72)

    popularity_rows = db.execute(
        select(RecommendationSignal.repertoire_item_id, func.sum(RecommendationSignal.weight))
        .where(
            RecommendationSignal.surface == "repertoire",
            RecommendationSignal.organization_id == membership.organization_id,
            RecommendationSignal.program_id == membership.program_id,
            RecommendationSignal.event_id == membership.event_id,
            RecommendationSignal.store_id == membership.store_id,
            RecommendationSignal.repertoire_item_id.in_(repertoire_item_ids),
            RecommendationSignal.occurred_at >= cutoff_30d,
        )
        .group_by(RecommendationSignal.repertoire_item_id)
    ).all()

    recent_rows = db.execute(
        select(RecommendationSignal.repertoire_item_id, func.sum(RecommendationSignal.weight))
        .where(
            RecommendationSignal.surface == "repertoire",
            RecommendationSignal.organization_id == membership.organization_id,
            RecommendationSignal.program_id == membership.program_id,
            RecommendationSignal.event_id == membership.event_id,
            RecommendationSignal.store_id == membership.store_id,
            RecommendationSignal.repertoire_item_id.in_(repertoire_item_ids),
            RecommendationSignal.occurred_at >= cutoff_72h,
        )
        .group_by(RecommendationSignal.repertoire_item_id)
    ).all()

    popularity_map = {item_id: float(total or 0) for item_id, total in popularity_rows if item_id}
    recent_map = {item_id: float(total or 0) for item_id, total in recent_rows if item_id}
    return popularity_map, recent_map


def get_directory_tags(db: Session, directory_entry_ids: list[str]) -> dict[str, set[str]]:
    tag_map: dict[str, set[str]] = {entry_id: set() for entry_id in directory_entry_ids}
    if not directory_entry_ids:
        return tag_map
    rows = db.execute(
        select(DirectoryEntryTag.directory_entry_id, Tag.name)
        .join(Tag, Tag.id == DirectoryEntryTag.tag_id)
        .where(DirectoryEntryTag.directory_entry_id.in_(directory_entry_ids))
    ).all()
    for entry_id, tag_name in rows:
        tag_map.setdefault(entry_id, set()).add(tag_name.lower())
    return tag_map


def get_repertoire_tags(db: Session, repertoire_item_ids: list[str]) -> dict[str, set[str]]:
    tag_map: dict[str, set[str]] = {item_id: set() for item_id in repertoire_item_ids}
    if not repertoire_item_ids:
        return tag_map
    rows = db.execute(
        select(RepertoireItemTag.repertoire_item_id, Tag.name)
        .join(Tag, Tag.id == RepertoireItemTag.tag_id)
        .where(RepertoireItemTag.repertoire_item_id.in_(repertoire_item_ids))
    ).all()
    for item_id, tag_name in rows:
        tag_map.setdefault(item_id, set()).add(tag_name.lower())
    return tag_map


def get_active_pins(db: Session, membership: Membership, surface: str) -> list[RecommendationFeaturedPin]:
    now = datetime.now(UTC)
    return db.scalars(
        select(RecommendationFeaturedPin)
        .where(
            RecommendationFeaturedPin.organization_id == membership.organization_id,
            RecommendationFeaturedPin.program_id == membership.program_id,
            RecommendationFeaturedPin.event_id == membership.event_id,
            RecommendationFeaturedPin.store_id == membership.store_id,
            RecommendationFeaturedPin.surface == surface,
            or_(RecommendationFeaturedPin.expires_at.is_(None), RecommendationFeaturedPin.expires_at >= now),
        )
        .order_by(RecommendationFeaturedPin.created_at.desc())
    ).all()


def pairing_allows_directory_entry(
    db: Session,
    membership: Membership,
    *,
    directory_entry_id: str,
    repertoire_item_id: str,
) -> bool:
    scoped_rules = db.scalars(
        select(PairingRule).where(
            PairingRule.organization_id == membership.organization_id,
            PairingRule.program_id == membership.program_id,
            PairingRule.event_id == membership.event_id,
            PairingRule.store_id == membership.store_id,
            PairingRule.repertoire_item_id == repertoire_item_id,
        )
    ).all()

    for rule in scoped_rules:
        if rule.directory_entry_id == directory_entry_id and rule.effect == "block":
            return False

    has_allowlist = any(rule.effect == "allow" for rule in scoped_rules)
    if not has_allowlist:
        return True

    return any(rule.effect == "allow" and rule.directory_entry_id == directory_entry_id for rule in scoped_rules)


def pairing_allows_repertoire_item(
    db: Session,
    membership: Membership,
    *,
    directory_entry_id: str,
    repertoire_item_id: str,
) -> bool:
    return pairing_allows_directory_entry(
        db,
        membership,
        directory_entry_id=directory_entry_id,
        repertoire_item_id=repertoire_item_id,
    )


def verify_directory_entry_in_scope(db: Session, membership: Membership, entry_id: str) -> DirectoryEntry:
    entry = db.scalar(select(DirectoryEntry).where(DirectoryEntry.id == entry_id, *_scope_filter_for_entries(membership)))
    if not entry:
        raise AppError(code="VALIDATION_ERROR", message="Directory entry is out of scope", status_code=404)
    return entry


def verify_repertoire_item_in_scope(db: Session, membership: Membership, item_id: str) -> RepertoireItem:
    item = db.scalar(select(RepertoireItem).where(RepertoireItem.id == item_id, *_scope_filter_for_repertoire(membership)))
    if not item:
        raise AppError(code="VALIDATION_ERROR", message="Repertoire item is out of scope", status_code=404)
    return item


def _record_runtime_signals(
    db: Session,
    membership: Membership,
    *,
    user_id: str,
    surface: str,
    directory_entry_ids: list[str] | None,
    repertoire_item_ids: list[str] | None,
    signal_type: str,
    weight: float,
) -> None:
    now = datetime.now(UTC)
    for entry_id in directory_entry_ids or []:
        db.add(
            RecommendationSignal(
                organization_id=membership.organization_id,
                program_id=membership.program_id,
                event_id=membership.event_id,
                store_id=membership.store_id,
                surface=surface,
                user_id=user_id,
                directory_entry_id=entry_id,
                repertoire_item_id=None,
                signal_type=signal_type,
                weight=weight,
                occurred_at=now,
                created_at=now,
            )
        )

    for item_id in repertoire_item_ids or []:
        db.add(
            RecommendationSignal(
                organization_id=membership.organization_id,
                program_id=membership.program_id,
                event_id=membership.event_id,
                store_id=membership.store_id,
                surface=surface,
                user_id=user_id,
                directory_entry_id=None,
                repertoire_item_id=item_id,
                signal_type=signal_type,
                weight=weight,
                occurred_at=now,
                created_at=now,
            )
        )


def record_directory_search_impressions(
    db: Session,
    membership: Membership,
    *,
    user_id: str,
    directory_entry_ids: list[str],
) -> None:
    _record_runtime_signals(
        db,
        membership,
        user_id=user_id,
        surface="directory",
        directory_entry_ids=directory_entry_ids,
        repertoire_item_ids=None,
        signal_type="search_impression",
        weight=1.0,
    )


def record_repertoire_search_impressions(
    db: Session,
    membership: Membership,
    *,
    user_id: str,
    repertoire_item_ids: list[str],
) -> None:
    _record_runtime_signals(
        db,
        membership,
        user_id=user_id,
        surface="repertoire",
        directory_entry_ids=None,
        repertoire_item_ids=repertoire_item_ids,
        signal_type="search_impression",
        weight=1.0,
    )
