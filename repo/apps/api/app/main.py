from __future__ import annotations

import logging
import os
import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.router import build_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, sanitize_exception_for_log
from app.core.rate_limit import enforce_rate_limits, extract_device_ip, parse_trusted_proxy_cidrs, retry_after_seconds
from app.core.security import decode_session_token
from app.db.init_data import seed_baseline_data
from app.db.session import get_engine
from app.operations.backups import run_nightly_backups_if_due
from app.operations.compliance import count_overdue_recovery_drill_scopes, prune_audit_events_for_retention

configure_logging()
logger = logging.getLogger(__name__)


def current_utc_time() -> datetime:
    return datetime.now(UTC)


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_engine()
    with Session(engine) as session:
        settings = get_settings()
        if settings.demo_seed_on_startup:
            if settings.is_development_environment:
                seed_baseline_data(session)
                logger.info("Demo baseline data seeded at startup")
            else:
                logger.warning(
                    "Startup demo seeding requested but skipped outside development/test environments",
                    extra={"environment": settings.environment},
                )
        try:
            pruned_events = prune_audit_events_for_retention(session, retention_days=settings.audit_retention_days)
            overdue_scopes = count_overdue_recovery_drill_scopes(
                session,
                interval_days=settings.recovery_drill_interval_days,
            )
            if pruned_events > 0:
                session.commit()
            logger.info(
                "Operations compliance check completed",
                extra={
                    "audit_events_pruned": pruned_events,
                    "audit_retention_days": settings.audit_retention_days,
                    "overdue_recovery_drill_scopes": overdue_scopes,
                    "recovery_drill_interval_days": settings.recovery_drill_interval_days,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Operations compliance check failed", extra=sanitize_exception_for_log(exc))
        try:
            nightly_runs = run_nightly_backups_if_due(session)
            if nightly_runs:
                logger.info("Nightly backup runs completed", extra={"count": nightly_runs})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Nightly backup run failed", extra=sanitize_exception_for_log(exc))
    logger.info("API startup complete")
    yield
    logger.info("API shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="HarmonyHub API", version="0.1.0", lifespan=lifespan)
    route_coverage_file = os.getenv("HH_ROUTE_COVERAGE_FILE", "").strip()
    trusted_proxy_networks = parse_trusted_proxy_cidrs(settings.trusted_proxy_cidrs)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://localhost:9443", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        if route_coverage_file:
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            payload = {
                "method": request.method,
                "route_path": route_path,
                "request_path": request.url.path,
                "test_id": os.getenv("PYTEST_CURRENT_TEST", ""),
            }
            try:
                with open(route_coverage_file, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, sort_keys=True) + "\n")
            except Exception:  # noqa: BLE001
                logger.exception("Failed to write route coverage hit")

        return response

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        api_prefix = settings.api_prefix
        path = request.url.path
        if not path.startswith(api_prefix):
            return await call_next(request)
        if path in {f"{api_prefix}/health/live", f"{api_prefix}/health/ready"}:
            return await call_next(request)

        now = current_utc_time()
        ip_address = extract_device_ip(request, trusted_proxy_networks=trusted_proxy_networks)

        user_id: str | None = None
        token = request.cookies.get(settings.session_cookie_name)
        if token:
            try:
                user_id = decode_session_token(token).get("sub")
            except Exception:  # noqa: BLE001
                user_id = None

        with Session(get_engine()) as db:
            evaluation = enforce_rate_limits(
                db,
                now=now,
                ip_address=ip_address,
                ip_limit=settings.rate_limit_ip_per_min,
                user_id=user_id,
                user_limit=settings.rate_limit_user_per_min,
            )

        if evaluation.exceeded_scope:
            snapshot = evaluation.user if evaluation.exceeded_scope == "user" else evaluation.ip
            assert snapshot is not None
            retry_after = retry_after_seconds(snapshot, now)
            rate_limit_request_id = str(uuid.uuid4())
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded",
                        "details": {
                            "scope": snapshot.scope,
                            "limit": snapshot.limit,
                            "window_seconds": 60,
                            "remaining": snapshot.remaining,
                            "retry_after_seconds": retry_after,
                            "reset_at": snapshot.reset_at.isoformat(),
                        },
                        "request_id": rate_limit_request_id,
                    }
                },
                headers={
                    "X-Request-ID": rate_limit_request_id,
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Policy": (
                        f"user;w=60;limit={settings.rate_limit_user_per_min}, "
                        f"ip;w=60;limit={settings.rate_limit_ip_per_min}"
                    ),
                    "X-RateLimit-Scope": snapshot.scope,
                    "X-RateLimit-Limit": str(snapshot.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(snapshot.reset_at.timestamp())),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Policy"] = (
            f"user;w=60;limit={settings.rate_limit_user_per_min}, ip;w=60;limit={settings.rate_limit_ip_per_min}"
        )
        response.headers["X-RateLimit-IP-Limit"] = str(evaluation.ip.limit)
        response.headers["X-RateLimit-IP-Remaining"] = str(evaluation.ip.remaining)
        response.headers["X-RateLimit-IP-Reset"] = str(int(evaluation.ip.reset_at.timestamp()))
        if evaluation.user:
            response.headers["X-RateLimit-User-Limit"] = str(evaluation.user.limit)
            response.headers["X-RateLimit-User-Remaining"] = str(evaluation.user.remaining)
            response.headers["X-RateLimit-User-Reset"] = str(int(evaluation.user.reset_at.timestamp()))
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details or {},
                    "request_id": str(uuid.uuid4()),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception):
        logger.exception("Unhandled error", extra=sanitize_exception_for_log(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Unexpected server error",
                    "details": {},
                    "request_id": str(uuid.uuid4()),
                }
            },
        )

    app.include_router(build_router(), prefix=settings.api_prefix)
    return app


app = create_app()
