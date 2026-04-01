from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development", alias="HH_ENVIRONMENT")
    api_prefix: str = Field(default="/api/v1", alias="HH_API_PREFIX")
    log_level: str = Field(default="INFO", alias="HH_LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+psycopg2://harmonyhub:harmonyhub_dev@db:5432/harmonyhub",
        alias="DATABASE_URL",
    )

    jwt_secret: str = Field(default="change-me", alias="HH_JWT_SECRET")
    jwt_expire_minutes: int = Field(default=480, alias="HH_JWT_EXPIRE_MINUTES")
    pickup_code_ttl_seconds: int = Field(default=300, alias="HH_PICKUP_CODE_TTL_SECONDS")

    cookie_secure: bool = Field(default=True, alias="HH_COOKIE_SECURE")
    session_cookie_name: str = "hh_session"
    csrf_cookie_name: str = "hh_csrf"

    bootstrap_admin_username: str = Field(default="admin", alias="HH_BOOTSTRAP_ADMIN_USERNAME")
    bootstrap_admin_password: str = Field(default="admin123!", alias="HH_BOOTSTRAP_ADMIN_PASSWORD")

    export_dir: str = Field(default="/tmp/harmonyhub_exports", alias="HH_EXPORT_DIR")
    backup_dir: str = Field(default="/tmp/harmonyhub_backups", alias="HH_BACKUP_DIR")
    backup_offline_medium_dir: str = Field(default="/tmp/harmonyhub_offline_medium", alias="HH_BACKUP_OFFLINE_MEDIUM_DIR")
    backup_nightly_enabled: bool = Field(default=True, alias="HH_BACKUP_NIGHTLY_ENABLED")
    backup_nightly_hour_utc: int = Field(default=2, alias="HH_BACKUP_NIGHTLY_HOUR_UTC")
    audit_retention_days: int = Field(default=365, ge=1, alias="HH_AUDIT_RETENTION_DAYS")
    recovery_drill_interval_days: int = Field(default=90, ge=1, alias="HH_RECOVERY_DRILL_INTERVAL_DAYS")
    trusted_proxy_cidrs: str = Field(default="", alias="HH_TRUSTED_PROXY_CIDRS")
    rate_limit_user_per_min: int = Field(default=60, ge=1, alias="HH_RATE_LIMIT_USER_PER_MIN")
    rate_limit_ip_per_min: int = Field(default=300, ge=1, alias="HH_RATE_LIMIT_IP_PER_MIN")
    data_encryption_key: str = Field(default="dev-only-data-encryption-key", alias="HH_DATA_ENCRYPTION_KEY")

    @model_validator(mode="after")
    def validate_non_development_security_defaults(self) -> "Settings":
        environment = self.environment.lower().strip()
        if environment in {"development", "dev", "test", "testing", "local"}:
            return self

        weak_jwt_defaults = {"change-me", "change-me-in-real-deployments", "test-secret"}
        if self.jwt_secret.strip() in weak_jwt_defaults:
            raise ValueError("HH_JWT_SECRET must be overridden for non-development environments")

        if self.bootstrap_admin_password.strip() == "admin123!":
            raise ValueError("HH_BOOTSTRAP_ADMIN_PASSWORD must be overridden for non-development environments")

        weak_data_encryption_defaults = {
            "dev-only-data-encryption-key",
            "change-me",
            "change-me-in-real-deployments",
        }
        if self.data_encryption_key.strip() in weak_data_encryption_defaults:
            raise ValueError("HH_DATA_ENCRYPTION_KEY must be overridden for non-development environments")

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
