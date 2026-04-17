from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine, reset_engine_for_tests
from app.main import create_app


def _prepare_env(monkeypatch, *, database_url: str, environment: str, seed_on_startup: bool) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("HH_ENVIRONMENT", environment)
    monkeypatch.setenv("HH_DEMO_SEED_ON_STARTUP", "true" if seed_on_startup else "false")
    monkeypatch.setenv("HH_COOKIE_SECURE", "false")
    monkeypatch.setenv("HH_JWT_SECRET", "test-jwt-secret-strong")
    monkeypatch.setenv("HH_DATA_ENCRYPTION_KEY", "test-data-encryption-key-strong")
    monkeypatch.setenv("HH_BOOTSTRAP_ADMIN_PASSWORD", "test-admin-pass-strong")
    get_settings.cache_clear()
    reset_engine_for_tests()


def test_alembic_upgrade_head_contains_membership_freeze_schema(monkeypatch):
    database_url = os.getenv("HH_TEST_POSTGRES_DATABASE_URL", "").strip()
    if not database_url.startswith("postgresql"):
        pytest.skip("Migration-path verification requires HH_TEST_POSTGRES_DATABASE_URL")

    _prepare_env(monkeypatch, database_url=database_url, environment="test", seed_on_startup=False)

    api_root = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(api_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(api_root / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_config, "head")

    inspector = inspect(create_engine(database_url))
    membership_columns = {col["name"] for col in inspector.get_columns("memberships")}
    user_columns = {col["name"] for col in inspector.get_columns("users")}

    assert {"is_frozen", "frozen_at", "freeze_reason", "frozen_by_user_id", "unfrozen_at", "unfrozen_by_user_id"}.issubset(
        membership_columns
    )
    assert {"frozen_at", "freeze_reason", "frozen_by_user_id", "unfrozen_at", "unfrozen_by_user_id"}.isdisjoint(user_columns)


def test_startup_seed_requires_explicit_dev_opt_in(tmp_path, monkeypatch):
    db_path = tmp_path / "startup_seed.sqlite3"
    database_url = f"sqlite:///{db_path}"

    _prepare_env(monkeypatch, database_url=database_url, environment="development", seed_on_startup=False)
    Base.metadata.create_all(bind=get_engine())

    with TestClient(create_app()) as client:
        login_without_seed = client.post("/api/v1/auth/login", json={"username": "staff", "password": "staff123!"})
        assert login_without_seed.status_code == 401

    _prepare_env(monkeypatch, database_url=database_url, environment="development", seed_on_startup=True)
    with TestClient(create_app()) as client:
        login_with_dev_seed = client.post("/api/v1/auth/login", json={"username": "staff", "password": "staff123!"})
        assert login_with_dev_seed.status_code == 200

    prod_db_path = tmp_path / "startup_seed_production.sqlite3"
    prod_database_url = f"sqlite:///{prod_db_path}"
    _prepare_env(monkeypatch, database_url=prod_database_url, environment="production", seed_on_startup=True)
    Base.metadata.create_all(bind=get_engine())
    with TestClient(create_app()) as client:
        login_with_prod_seed = client.post("/api/v1/auth/login", json={"username": "staff", "password": "staff123!"})
        assert login_with_prod_seed.status_code == 401
