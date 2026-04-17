from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://harmonyhub:harmonyhub_dev@db:5432/harmonyhub_test")
os.environ["HH_COOKIE_SECURE"] = "false"
os.environ["HH_JWT_SECRET"] = "test-secret"
os.environ["HH_BACKUP_NIGHTLY_ENABLED"] = "false"

from app.core.config import get_settings  # noqa: E402
from app.core.field_encryption import get_field_fernet  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.init_data import seed_baseline_data  # noqa: E402
from app.db.session import get_engine, reset_engine_for_tests  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_state(request: pytest.FixtureRequest):
    if request.node.name == "test_alembic_upgrade_head_contains_membership_freeze_schema":
        yield
        return

    get_settings.cache_clear()
    get_field_fernet.cache_clear()
    reset_engine_for_tests()
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        seed_baseline_data(session)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)
