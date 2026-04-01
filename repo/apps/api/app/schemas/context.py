from __future__ import annotations

from pydantic import BaseModel


class ContextChoice(BaseModel):
    organization_id: str
    organization_name: str
    program_id: str
    program_name: str
    event_id: str
    event_name: str
    store_id: str
    store_name: str
    role: str


class ActiveContext(BaseModel):
    organization_id: str
    program_id: str
    event_id: str
    store_id: str
    role: str


class ContextSetRequest(BaseModel):
    organization_id: str
    program_id: str
    event_id: str
    store_id: str


class ContextSetResponse(BaseModel):
    status: str
    active_context: ActiveContext


class DashboardResponse(BaseModel):
    event_name: str
    store_name: str
    organization_name: str
    user_role: str
    permissions: list[str]
    abac_enforced: bool
    notes: list[str]
