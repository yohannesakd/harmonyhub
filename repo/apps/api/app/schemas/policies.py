from __future__ import annotations

from pydantic import BaseModel, Field


class AbacSurfaceSettingResponse(BaseModel):
    id: str
    organization_id: str
    surface: str
    enabled: bool


class AbacSurfaceSettingUpsertRequest(BaseModel):
    enabled: bool


class AbacRuleCreateRequest(BaseModel):
    surface: str = Field(min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=64)
    effect: str = Field(pattern="^(allow|deny)$")
    priority: int = Field(default=100, ge=1, le=1000)
    role: str | None = Field(default=None, max_length=32)
    subject_department: str | None = Field(default=None, max_length=64)
    subject_grade: str | None = Field(default=None, max_length=32)
    subject_class: str | None = Field(default=None, max_length=64)
    program_id: str | None = None
    event_id: str | None = None
    store_id: str | None = None
    resource_department: str | None = Field(default=None, max_length=64)
    resource_grade: str | None = Field(default=None, max_length=32)
    resource_class: str | None = Field(default=None, max_length=64)
    resource_field: str | None = Field(default=None, max_length=64)


class AbacRuleResponse(BaseModel):
    id: str
    organization_id: str
    surface: str
    action: str
    effect: str
    priority: int
    role: str | None
    subject_department: str | None
    subject_grade: str | None
    subject_class: str | None
    program_id: str | None
    event_id: str | None
    store_id: str | None
    resource_department: str | None
    resource_grade: str | None
    resource_class: str | None
    resource_field: str | None


class AbacSimulationContext(BaseModel):
    program_id: str | None = None
    event_id: str | None = None
    store_id: str | None = None


class AbacSimulationSubject(BaseModel):
    department: str | None = None
    grade: str | None = None
    class_code: str | None = None


class AbacSimulationResource(BaseModel):
    department: str | None = None
    grade: str | None = None
    class_code: str | None = None
    field: str | None = None


class AbacSimulationRequest(BaseModel):
    surface: str
    action: str
    context: AbacSimulationContext = Field(default_factory=AbacSimulationContext)
    role: str
    subject: AbacSimulationSubject = Field(default_factory=AbacSimulationSubject)
    resource: AbacSimulationResource = Field(default_factory=AbacSimulationResource)


class AbacSimulationResponse(BaseModel):
    allowed: bool
    enforced: bool
    reason: str
    matched_rule_id: str | None
