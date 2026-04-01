from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.context import ActiveContext, ContextChoice


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=255)
    totp_code: str | None = Field(default=None, max_length=12)


class UserSummary(BaseModel):
    id: str
    username: str
    is_active: bool
    mfa_totp_enabled: bool


class LoginResponse(BaseModel):
    user: UserSummary
    csrf_token: str
    active_context: ActiveContext | None
    permissions: list[str]


class MeResponse(BaseModel):
    user: UserSummary
    active_context: ActiveContext | None
    permissions: list[str]
    available_contexts: list[ContextChoice]


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class TotpCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class TotpVerifyResponse(BaseModel):
    valid: bool
    mfa_totp_enabled: bool
