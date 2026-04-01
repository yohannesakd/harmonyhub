from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AccountStatusResponse(BaseModel):
    id: str
    username: str
    is_active: bool
    is_frozen: bool
    frozen_at: datetime | None
    freeze_reason: str | None
    frozen_by_user_id: str | None
    unfrozen_at: datetime | None
    unfrozen_by_user_id: str | None


class FreezeAccountRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


class UnfreezeAccountRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
