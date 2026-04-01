from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import get_engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready"}
