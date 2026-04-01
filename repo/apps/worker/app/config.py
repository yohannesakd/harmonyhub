from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    log_level: str = Field(default="INFO", alias="HH_LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+psycopg2://harmonyhub:harmonyhub_dev@db:5432/harmonyhub",
        alias="DATABASE_URL",
    )
    offline_backup_medium_path: str = Field(default="/backup/offline-medium", alias="HH_OFFLINE_BACKUP_MEDIUM_PATH")
    heartbeat_seconds: int = Field(default=30, alias="HH_WORKER_HEARTBEAT_SECONDS")
    backup_check_seconds: int = Field(default=300, alias="HH_WORKER_BACKUP_CHECK_SECONDS")
    operations_check_seconds: int = Field(default=3600, alias="HH_WORKER_OPERATIONS_CHECK_SECONDS")
    audit_retention_days: int = Field(default=365, ge=1, alias="HH_AUDIT_RETENTION_DAYS")
    recovery_drill_interval_days: int = Field(default=90, ge=1, alias="HH_RECOVERY_DRILL_INTERVAL_DAYS")


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    return WorkerSettings()
