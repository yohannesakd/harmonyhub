from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AvailabilityWindowResponse(BaseModel):
    starts_at: datetime
    ends_at: datetime


class ContactResponse(BaseModel):
    email: str | None
    phone: str | None
    address_line1: str | None
    masked: bool


class DirectoryEntryCardResponse(BaseModel):
    id: str
    display_name: str
    stage_name: str | None
    region: str
    tags: list[str]
    repertoire: list[str]
    availability_windows: list[AvailabilityWindowResponse]
    contact: ContactResponse
    can_reveal_contact: bool


class DirectoryEntryDetailResponse(DirectoryEntryCardResponse):
    biography: str | None


class DirectorySearchResponse(BaseModel):
    results: list[DirectoryEntryCardResponse]
    total: int


class DirectoryContactRevealResponse(BaseModel):
    entry_id: str
    contact: ContactResponse
