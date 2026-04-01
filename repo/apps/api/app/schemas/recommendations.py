from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.directory import ContactResponse

ScopeType = Literal["organization", "program", "event_store"]
RecommendationSurface = Literal["directory", "repertoire"]


class RecommendationWeights(BaseModel):
    popularity_30d: float = Field(ge=0)
    recent_activity_72h: float = Field(ge=0)
    tag_match: float = Field(ge=0)


class RecommendationEnabledModes(BaseModel):
    popularity_30d: bool = True
    recent_activity_72h: bool = True
    tag_match: bool = True


class RecommendationScope(BaseModel):
    scope: ScopeType
    organization_id: str
    program_id: str | None = None
    event_id: str | None = None
    store_id: str | None = None


class RecommendationConfigResponse(BaseModel):
    id: str | None
    scope: RecommendationScope
    inherited_from_scope: ScopeType | None = None
    enabled_modes: RecommendationEnabledModes
    weights: RecommendationWeights
    pins_enabled: bool
    max_pins: int
    pin_ttl_hours: int | None
    enforce_pairing_rules: bool
    allow_staff_event_store_manage: bool
    updated_at: datetime


class RecommendationConfigUpsertRequest(BaseModel):
    scope: ScopeType
    enabled_modes: RecommendationEnabledModes
    weights: RecommendationWeights
    pins_enabled: bool = True
    max_pins: int = Field(default=20, ge=1, le=100)
    pin_ttl_hours: int | None = Field(default=None, ge=1, le=168)
    enforce_pairing_rules: bool = True
    allow_staff_event_store_manage: bool = False


class RecommendationConfigValidateResponse(BaseModel):
    valid: bool
    normalized_weights: RecommendationWeights


class RecommendationScoreBreakdown(BaseModel):
    popularity_30d: float
    recent_activity_72h: float
    tag_match: float
    total: float


class DirectoryRecommendationItem(BaseModel):
    entry_id: str
    display_name: str
    region: str
    tags: list[str]
    repertoire: list[str]
    contact: ContactResponse
    pinned: bool
    score: RecommendationScoreBreakdown


class RepertoireRecommendationItem(BaseModel):
    repertoire_item_id: str
    title: str
    composer: str | None
    tags: list[str]
    performers: list[str]
    pinned: bool
    score: RecommendationScoreBreakdown


class DirectoryRecommendationsResponse(BaseModel):
    config_scope: ScopeType
    results: list[DirectoryRecommendationItem]


class RepertoireRecommendationsResponse(BaseModel):
    config_scope: ScopeType
    results: list[RepertoireRecommendationItem]


class FeaturedPinRequest(BaseModel):
    surface: RecommendationSurface
    expires_at: datetime | None = None


class FeaturedPinResponse(BaseModel):
    id: str
    surface: RecommendationSurface
    directory_entry_id: str | None
    repertoire_item_id: str | None
    expires_at: datetime | None
    created_at: datetime


class PairingRuleCreateRequest(BaseModel):
    directory_entry_id: str
    repertoire_item_id: str
    note: str | None = Field(default=None, max_length=255)


class PairingRuleResponse(BaseModel):
    id: str
    effect: Literal["allow", "block"]
    directory_entry_id: str
    repertoire_item_id: str
    note: str | None
    created_at: datetime
