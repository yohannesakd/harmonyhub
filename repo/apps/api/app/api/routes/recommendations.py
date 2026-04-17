from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthorizedMembership, authorize_for_active_context, verify_csrf, verify_replay_headers
from app.authz.abac import get_policy_evaluator
from app.authz.rbac import Permission
from app.core.errors import AppError
from app.directory.access import (
    build_directory_subject,
    is_directory_row_allowed,
    serialize_directory_contact_with_field_scope,
)
from app.db.models import (
    DirectoryEntry,
    DirectoryEntryRepertoireItem,
    DirectoryEntryTag,
    PairingRule,
    RecommendationConfig,
    RecommendationFeaturedPin,
    RepertoireItem,
    RepertoireItemTag,
    Tag,
)
from app.db.session import get_db_session
from app.recommendations.engine import (
    assert_config_scope_permission,
    get_active_pins,
    get_directory_signal_scores,
    get_directory_tags,
    get_exact_config_for_scope,
    get_repertoire_signal_scores,
    get_repertoire_tags,
    normalize_weights,
    pairing_allows_directory_entry,
    pairing_allows_repertoire_item,
    resolve_config_for_requested_scope,
    resolve_effective_config,
    verify_directory_entry_in_scope,
    verify_repertoire_item_in_scope,
)
from app.schemas.recommendations import (
    DirectoryRecommendationItem,
    DirectoryRecommendationsResponse,
    FeaturedPinRequest,
    FeaturedPinResponse,
    PairingRuleCreateRequest,
    PairingRuleResponse,
    RecommendationConfigResponse,
    RecommendationConfigUpsertRequest,
    RecommendationConfigValidateResponse,
    RecommendationEnabledModes,
    RecommendationScoreBreakdown,
    RecommendationScope,
    RecommendationWeights,
    RepertoireRecommendationItem,
    RepertoireRecommendationsResponse,
    ScopeType,
)

recommendations_router = APIRouter(prefix="/recommendations", tags=["recommendations"])
pairing_router = APIRouter(prefix="/pairing-rules", tags=["pairing-rules"])


def _scope_payload(scope: ScopeType, authorized: AuthorizedMembership) -> RecommendationScope:
    membership = authorized.membership
    if scope == "organization":
        return RecommendationScope(scope=scope, organization_id=membership.organization_id)
    if scope == "program":
        return RecommendationScope(
            scope=scope,
            organization_id=membership.organization_id,
            program_id=membership.program_id,
        )
    return RecommendationScope(
        scope=scope,
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
    )


def _effective_config_to_response(
    *,
    authorized: AuthorizedMembership,
    effective,
    scope: ScopeType,
) -> RecommendationConfigResponse:
    updated_at = effective.config.updated_at if effective.config else datetime.now(UTC)
    config_id: str | None = None
    if effective.config and effective.inherited_from_scope is None:
        config_id = effective.config.id
    return RecommendationConfigResponse(
        id=config_id,
        scope=_scope_payload(scope, authorized),
        inherited_from_scope=effective.inherited_from_scope,
        enabled_modes=effective.enabled_modes,
        weights=effective.weights,
        pins_enabled=effective.pins_enabled,
        max_pins=effective.max_pins,
        pin_ttl_hours=effective.pin_ttl_hours,
        enforce_pairing_rules=effective.enforce_pairing_rules,
        allow_staff_event_store_manage=effective.allow_staff_event_store_manage,
        updated_at=updated_at,
    )


def _score(
    *,
    enabled_modes: RecommendationEnabledModes,
    weights: RecommendationWeights,
    popularity: float,
    recent: float,
    tag_match: float,
) -> RecommendationScoreBreakdown:
    popularity_value = popularity * weights.popularity_30d if enabled_modes.popularity_30d else 0
    recent_value = recent * weights.recent_activity_72h if enabled_modes.recent_activity_72h else 0
    tag_value = tag_match * weights.tag_match if enabled_modes.tag_match else 0
    return RecommendationScoreBreakdown(
        popularity_30d=round(popularity_value, 5),
        recent_activity_72h=round(recent_value, 5),
        tag_match=round(tag_value, 5),
        total=round(popularity_value + recent_value + tag_value, 5),
    )


@recommendations_router.get("/config", response_model=RecommendationConfigResponse)
def get_recommendation_config(
    scope: ScopeType = Query(default="event_store"),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_VIEW, surface="recommendations", action="view_config")
    ),
    db: Session = Depends(get_db_session),
) -> RecommendationConfigResponse:
    effective = resolve_config_for_requested_scope(db, authorized.membership, scope)
    return _effective_config_to_response(authorized=authorized, effective=effective, scope=scope)


@recommendations_router.get("/config/effective", response_model=RecommendationConfigResponse)
def get_effective_recommendation_config(
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_VIEW, surface="recommendations", action="view_config")
    ),
    db: Session = Depends(get_db_session),
) -> RecommendationConfigResponse:
    effective = resolve_effective_config(db, authorized.membership)
    return _effective_config_to_response(authorized=authorized, effective=effective, scope=effective.scope)


@recommendations_router.post("/config/validate", response_model=RecommendationConfigValidateResponse)
def validate_recommendation_config(payload: RecommendationConfigUpsertRequest) -> RecommendationConfigValidateResponse:
    normalized = normalize_weights(payload.weights)
    return RecommendationConfigValidateResponse(valid=True, normalized_weights=normalized)


@recommendations_router.put("/config", response_model=RecommendationConfigResponse, dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)])
def upsert_recommendation_config(
    payload: RecommendationConfigUpsertRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_MANAGE, surface="recommendations", action="manage_config")
    ),
    db: Session = Depends(get_db_session),
) -> RecommendationConfigResponse:
    scope = payload.scope
    membership = authorized.membership
    assert_config_scope_permission(db, membership, scope)

    existing = get_exact_config_for_scope(db, membership, scope)
    weights = normalize_weights(payload.weights)

    if not existing:
        if scope == "organization":
            existing = RecommendationConfig(organization_id=membership.organization_id)
        elif scope == "program":
            existing = RecommendationConfig(
                organization_id=membership.organization_id,
                program_id=membership.program_id,
            )
        else:
            existing = RecommendationConfig(
                organization_id=membership.organization_id,
                program_id=membership.program_id,
                event_id=membership.event_id,
                store_id=membership.store_id,
            )

    existing.enabled_popularity_30d = payload.enabled_modes.popularity_30d
    existing.enabled_recent_activity_72h = payload.enabled_modes.recent_activity_72h
    existing.enabled_tag_match = payload.enabled_modes.tag_match
    existing.weight_popularity_30d = weights.popularity_30d
    existing.weight_recent_activity_72h = weights.recent_activity_72h
    existing.weight_tag_match = weights.tag_match
    existing.pins_enabled = payload.pins_enabled
    existing.max_pins = payload.max_pins
    existing.pin_ttl_hours = payload.pin_ttl_hours
    existing.enforce_pairing_rules = payload.enforce_pairing_rules
    existing.allow_staff_event_store_manage = payload.allow_staff_event_store_manage if scope in {"organization", "program"} else False
    existing.updated_by_user_id = membership.user_id
    existing.updated_at = datetime.now(UTC)

    db.add(existing)
    db.commit()
    db.refresh(existing)

    effective = resolve_config_for_requested_scope(db, membership, scope)
    return _effective_config_to_response(authorized=authorized, effective=effective, scope=scope)


@recommendations_router.get("/featured", response_model=list[FeaturedPinResponse])
def list_featured_pins(
    surface: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_VIEW, surface="recommendations", action="view_featured")
    ),
    db: Session = Depends(get_db_session),
) -> list[FeaturedPinResponse]:
    pins = get_active_pins(db, authorized.membership, surface)
    return [
        FeaturedPinResponse(
            id=pin.id,
            surface=pin.surface,
            directory_entry_id=pin.directory_entry_id,
            repertoire_item_id=pin.repertoire_item_id,
            expires_at=pin.expires_at,
            created_at=pin.created_at,
        )
        for pin in pins
    ]


@recommendations_router.post(
    "/featured/{target_id}",
    response_model=FeaturedPinResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def pin_featured_target(
    target_id: str,
    payload: FeaturedPinRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_MANAGE, surface="recommendations", action="manage_featured")
    ),
    db: Session = Depends(get_db_session),
) -> FeaturedPinResponse:
    membership = authorized.membership
    effective = resolve_effective_config(db, membership)
    if not effective.pins_enabled:
        raise AppError(code="FORBIDDEN", message="Featured pins are disabled by recommendation config", status_code=403)

    if payload.surface == "directory":
        verify_directory_entry_in_scope(db, membership, target_id)
        directory_entry_id = target_id
        repertoire_item_id = None
    else:
        verify_repertoire_item_in_scope(db, membership, target_id)
        directory_entry_id = None
        repertoire_item_id = target_id

    existing = db.scalar(
        select(RecommendationFeaturedPin).where(
            RecommendationFeaturedPin.organization_id == membership.organization_id,
            RecommendationFeaturedPin.program_id == membership.program_id,
            RecommendationFeaturedPin.event_id == membership.event_id,
            RecommendationFeaturedPin.store_id == membership.store_id,
            RecommendationFeaturedPin.surface == payload.surface,
            RecommendationFeaturedPin.directory_entry_id == directory_entry_id,
            RecommendationFeaturedPin.repertoire_item_id == repertoire_item_id,
        )
    )

    now = datetime.now(UTC)
    active_pins = get_active_pins(db, membership, payload.surface)
    if not existing and len(active_pins) >= effective.max_pins:
        raise AppError(code="VALIDATION_ERROR", message="Maximum number of featured pins reached", status_code=422)

    pin = existing or RecommendationFeaturedPin(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        surface=payload.surface,
        directory_entry_id=directory_entry_id,
        repertoire_item_id=repertoire_item_id,
        pinned_by_user_id=membership.user_id,
    )
    pin.created_at = now
    pin.expires_at = payload.expires_at
    if pin.expires_at is None and effective.pin_ttl_hours:
        pin.expires_at = now + timedelta(hours=effective.pin_ttl_hours)

    db.add(pin)
    db.commit()
    db.refresh(pin)

    return FeaturedPinResponse(
        id=pin.id,
        surface=pin.surface,
        directory_entry_id=pin.directory_entry_id,
        repertoire_item_id=pin.repertoire_item_id,
        expires_at=pin.expires_at,
        created_at=pin.created_at,
    )


@recommendations_router.delete(
    "/featured/{target_id}",
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def unpin_featured_target(
    target_id: str,
    surface: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_MANAGE, surface="recommendations", action="manage_featured")
    ),
    db: Session = Depends(get_db_session),
) -> dict:
    membership = authorized.membership
    where_clause = [
        RecommendationFeaturedPin.organization_id == membership.organization_id,
        RecommendationFeaturedPin.program_id == membership.program_id,
        RecommendationFeaturedPin.event_id == membership.event_id,
        RecommendationFeaturedPin.store_id == membership.store_id,
        RecommendationFeaturedPin.surface == surface,
    ]
    if surface == "directory":
        where_clause.append(RecommendationFeaturedPin.directory_entry_id == target_id)
    else:
        where_clause.append(RecommendationFeaturedPin.repertoire_item_id == target_id)

    pin = db.scalar(select(RecommendationFeaturedPin).where(*where_clause))
    if not pin:
        raise AppError(code="VALIDATION_ERROR", message="Featured pin not found", status_code=404)

    db.delete(pin)
    db.commit()
    return {"status": "unpinned"}


@recommendations_router.get("/directory", response_model=DirectoryRecommendationsResponse)
def recommend_directory(
    tags: list[str] = Query(default=[]),
    repertoire_item_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_VIEW, surface="recommendations", action="recommend_directory")
    ),
    db: Session = Depends(get_db_session),
) -> DirectoryRecommendationsResponse:
    membership = authorized.membership
    effective = resolve_effective_config(db, membership)
    subject = build_directory_subject(authorized.principal.user)
    row_evaluator = get_policy_evaluator(db, membership, surface="directory", action="search_row")
    field_evaluator = get_policy_evaluator(db, membership, surface="directory", action="contact_field_view")

    if repertoire_item_id:
        verify_repertoire_item_in_scope(db, membership, repertoire_item_id)

    entries = db.scalars(
        select(DirectoryEntry).where(
            DirectoryEntry.organization_id == membership.organization_id,
            DirectoryEntry.program_id == membership.program_id,
            DirectoryEntry.event_id == membership.event_id,
            DirectoryEntry.store_id == membership.store_id,
        )
    ).all()
    entries = [
        entry for entry in entries if is_directory_row_allowed(row_evaluator=row_evaluator, subject=subject, entry=entry)
    ]

    entry_ids = [entry.id for entry in entries]
    if not entry_ids:
        return DirectoryRecommendationsResponse(config_scope=effective.scope, results=[])

    requested_tags = {tag.strip().lower() for tag in tags if tag.strip()}
    entry_tags = get_directory_tags(db, entry_ids)
    popularity_map, recent_map = get_directory_signal_scores(db, membership, entry_ids)

    repertoire_map: dict[str, list[str]] = defaultdict(list)
    repertoire_rows = db.execute(
        select(DirectoryEntryRepertoireItem.directory_entry_id, RepertoireItem.title)
        .join(RepertoireItem, RepertoireItem.id == DirectoryEntryRepertoireItem.repertoire_item_id)
        .where(DirectoryEntryRepertoireItem.directory_entry_id.in_(entry_ids))
        .order_by(RepertoireItem.title.asc())
    ).all()
    for entry_id, title in repertoire_rows:
        repertoire_map[entry_id].append(title)

    pin_rows = get_active_pins(db, membership, "directory") if effective.pins_enabled else []
    active_pinned_ids = [pin.directory_entry_id for pin in pin_rows if pin.directory_entry_id][: effective.max_pins]
    pin_index = {entry_id: index for index, entry_id in enumerate(active_pinned_ids)}

    scored: list[tuple[int, int, float, DirectoryRecommendationItem]] = []
    for entry in entries:
        if effective.enforce_pairing_rules and repertoire_item_id:
            if not pairing_allows_directory_entry(
                db,
                membership,
                directory_entry_id=entry.id,
                repertoire_item_id=repertoire_item_id,
            ):
                continue

        tag_match = float(len(entry_tags.get(entry.id, set()).intersection(requested_tags)))
        score = _score(
            enabled_modes=effective.enabled_modes,
            weights=effective.weights,
            popularity=popularity_map.get(entry.id, 0.0),
            recent=recent_map.get(entry.id, 0.0),
            tag_match=tag_match,
        )
        is_pinned = entry.id in pin_index
        recommendation = DirectoryRecommendationItem(
            entry_id=entry.id,
            display_name=entry.display_name,
            region=entry.region,
            tags=sorted(entry_tags.get(entry.id, set())),
            repertoire=repertoire_map.get(entry.id, []),
            contact=serialize_directory_contact_with_field_scope(
                db,
                membership=membership,
                user=authorized.principal.user,
                entry=entry,
                masked=True,
                subject=subject,
                field_evaluator=field_evaluator,
            ),
            pinned=is_pinned,
            score=score,
        )
        scored.append(
            (
                0 if is_pinned else 1,
                pin_index.get(entry.id, 10_000),
                -score.total,
                recommendation,
            )
        )

    scored.sort(key=lambda item: (item[0], item[1], item[2], item[3].display_name.lower()))
    return DirectoryRecommendationsResponse(config_scope=effective.scope, results=[row[3] for row in scored[:limit]])


@recommendations_router.get("/repertoire", response_model=RepertoireRecommendationsResponse)
def recommend_repertoire(
    tags: list[str] = Query(default=[]),
    directory_entry_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_VIEW, surface="recommendations", action="recommend_repertoire")
    ),
    db: Session = Depends(get_db_session),
) -> RepertoireRecommendationsResponse:
    membership = authorized.membership
    effective = resolve_effective_config(db, membership)
    subject = build_directory_subject(authorized.principal.user)
    row_evaluator = get_policy_evaluator(db, membership, surface="directory", action="search_row")

    if directory_entry_id:
        selected_entry = verify_directory_entry_in_scope(db, membership, directory_entry_id)
        if not is_directory_row_allowed(row_evaluator=row_evaluator, subject=subject, entry=selected_entry):
            raise AppError(code="VALIDATION_ERROR", message="Directory entry is out of scope", status_code=404)

    items = db.scalars(
        select(RepertoireItem).where(
            RepertoireItem.organization_id == membership.organization_id,
            RepertoireItem.program_id == membership.program_id,
            RepertoireItem.event_id == membership.event_id,
            RepertoireItem.store_id == membership.store_id,
        )
    ).all()
    item_ids = [item.id for item in items]
    if not item_ids:
        return RepertoireRecommendationsResponse(config_scope=effective.scope, results=[])

    requested_tags = {tag.strip().lower() for tag in tags if tag.strip()}
    item_tags = get_repertoire_tags(db, item_ids)
    popularity_map, recent_map = get_repertoire_signal_scores(db, membership, item_ids)

    performer_map: dict[str, list[str]] = defaultdict(list)
    performer_rows = db.execute(
        select(DirectoryEntryRepertoireItem.repertoire_item_id, DirectoryEntry)
        .join(DirectoryEntry, DirectoryEntry.id == DirectoryEntryRepertoireItem.directory_entry_id)
        .where(
            DirectoryEntryRepertoireItem.repertoire_item_id.in_(item_ids),
            DirectoryEntry.organization_id == membership.organization_id,
            DirectoryEntry.program_id == membership.program_id,
            DirectoryEntry.event_id == membership.event_id,
            DirectoryEntry.store_id == membership.store_id,
        )
        .order_by(DirectoryEntry.display_name.asc())
    ).all()
    for item_id, performer_entry in performer_rows:
        if is_directory_row_allowed(row_evaluator=row_evaluator, subject=subject, entry=performer_entry):
            performer_map[item_id].append(performer_entry.display_name)

    pin_rows = get_active_pins(db, membership, "repertoire") if effective.pins_enabled else []
    active_pinned_ids = [pin.repertoire_item_id for pin in pin_rows if pin.repertoire_item_id][: effective.max_pins]
    pin_index = {item_id: index for index, item_id in enumerate(active_pinned_ids)}

    scored: list[tuple[int, int, float, RepertoireRecommendationItem]] = []
    for item in items:
        if effective.enforce_pairing_rules and directory_entry_id:
            if not pairing_allows_repertoire_item(
                db,
                membership,
                directory_entry_id=directory_entry_id,
                repertoire_item_id=item.id,
            ):
                continue

        tag_match = float(len(item_tags.get(item.id, set()).intersection(requested_tags)))
        score = _score(
            enabled_modes=effective.enabled_modes,
            weights=effective.weights,
            popularity=popularity_map.get(item.id, 0.0),
            recent=recent_map.get(item.id, 0.0),
            tag_match=tag_match,
        )
        is_pinned = item.id in pin_index
        recommendation = RepertoireRecommendationItem(
            repertoire_item_id=item.id,
            title=item.title,
            composer=item.composer,
            tags=sorted(item_tags.get(item.id, set())),
            performers=performer_map.get(item.id, []),
            pinned=is_pinned,
            score=score,
        )
        scored.append(
            (
                0 if is_pinned else 1,
                pin_index.get(item.id, 10_000),
                -score.total,
                recommendation,
            )
        )

    scored.sort(key=lambda item: (item[0], item[1], item[2], item[3].title.lower()))
    return RepertoireRecommendationsResponse(config_scope=effective.scope, results=[row[3] for row in scored[:limit]])


@pairing_router.get("", response_model=list[PairingRuleResponse])
def list_pairing_rules(
    effect: str | None = None,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_VIEW, surface="recommendations", action="view_pairing_rules")
    ),
    db: Session = Depends(get_db_session),
) -> list[PairingRuleResponse]:
    membership = authorized.membership
    query = select(PairingRule).where(
        PairingRule.organization_id == membership.organization_id,
        PairingRule.program_id == membership.program_id,
        PairingRule.event_id == membership.event_id,
        PairingRule.store_id == membership.store_id,
    )
    if effect:
        query = query.where(PairingRule.effect == effect)
    rules = db.scalars(query.order_by(PairingRule.created_at.desc())).all()
    return [
        PairingRuleResponse(
            id=rule.id,
            effect=rule.effect,
            directory_entry_id=rule.directory_entry_id,
            repertoire_item_id=rule.repertoire_item_id,
            note=rule.note,
            created_at=rule.created_at,
        )
        for rule in rules
    ]


def _create_pairing_rule(
    *,
    effect: str,
    payload: PairingRuleCreateRequest,
    authorized: AuthorizedMembership,
    db: Session,
) -> PairingRuleResponse:
    if effect not in {"allow", "block"}:
        raise AppError(code="VALIDATION_ERROR", message="Invalid pairing rule effect", status_code=422)

    membership = authorized.membership
    verify_directory_entry_in_scope(db, membership, payload.directory_entry_id)
    verify_repertoire_item_in_scope(db, membership, payload.repertoire_item_id)

    existing = db.scalar(
        select(PairingRule).where(
            PairingRule.organization_id == membership.organization_id,
            PairingRule.program_id == membership.program_id,
            PairingRule.event_id == membership.event_id,
            PairingRule.store_id == membership.store_id,
            PairingRule.directory_entry_id == payload.directory_entry_id,
            PairingRule.repertoire_item_id == payload.repertoire_item_id,
            PairingRule.effect == effect,
        )
    )
    if existing:
        return PairingRuleResponse(
            id=existing.id,
            effect=existing.effect,
            directory_entry_id=existing.directory_entry_id,
            repertoire_item_id=existing.repertoire_item_id,
            note=existing.note,
            created_at=existing.created_at,
        )

    rule = PairingRule(
        organization_id=membership.organization_id,
        program_id=membership.program_id,
        event_id=membership.event_id,
        store_id=membership.store_id,
        directory_entry_id=payload.directory_entry_id,
        repertoire_item_id=payload.repertoire_item_id,
        effect=effect,
        note=payload.note,
        created_by_user_id=membership.user_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return PairingRuleResponse(
        id=rule.id,
        effect=rule.effect,
        directory_entry_id=rule.directory_entry_id,
        repertoire_item_id=rule.repertoire_item_id,
        note=rule.note,
        created_at=rule.created_at,
    )


@pairing_router.post(
    "/allowlist",
    response_model=PairingRuleResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def create_allowlist_rule(
    payload: PairingRuleCreateRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_MANAGE, surface="recommendations", action="manage_pairing_rules")
    ),
    db: Session = Depends(get_db_session),
) -> PairingRuleResponse:
    return _create_pairing_rule(effect="allow", payload=payload, authorized=authorized, db=db)


@pairing_router.post(
    "/blocklist",
    response_model=PairingRuleResponse,
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def create_blocklist_rule(
    payload: PairingRuleCreateRequest,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_MANAGE, surface="recommendations", action="manage_pairing_rules")
    ),
    db: Session = Depends(get_db_session),
) -> PairingRuleResponse:
    return _create_pairing_rule(effect="block", payload=payload, authorized=authorized, db=db)


@pairing_router.delete(
    "/{rule_id}",
    dependencies=[Depends(verify_replay_headers), Depends(verify_csrf)],
)
def delete_pairing_rule(
    rule_id: str,
    authorized: AuthorizedMembership = Depends(
        authorize_for_active_context(Permission.RECOMMENDATIONS_MANAGE, surface="recommendations", action="manage_pairing_rules")
    ),
    db: Session = Depends(get_db_session),
) -> dict:
    membership = authorized.membership
    rule = db.scalar(
        select(PairingRule).where(
            PairingRule.id == rule_id,
            PairingRule.organization_id == membership.organization_id,
            PairingRule.program_id == membership.program_id,
            PairingRule.event_id == membership.event_id,
            PairingRule.store_id == membership.store_id,
        )
    )
    if not rule:
        raise AppError(code="VALIDATION_ERROR", message="Pairing rule not found", status_code=404)
    db.delete(rule)
    db.commit()
    return {"status": "deleted"}
