from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address, ip_network
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ApiRateLimitBucket

RATE_LIMIT_WINDOW_SECONDS = 60
TrustedProxyNetwork = IPv4Network | IPv6Network
IpAddress = IPv4Address | IPv6Address


@dataclass
class RateLimitSnapshot:
    scope: str
    limit: int
    remaining: int
    reset_at: datetime
    exceeded: bool


@dataclass
class RateLimitEvaluation:
    ip: RateLimitSnapshot
    user: RateLimitSnapshot | None
    exceeded_scope: str | None


def parse_trusted_proxy_cidrs(raw_value: str) -> tuple[TrustedProxyNetwork, ...]:
    cidrs: list[TrustedProxyNetwork] = []
    for candidate in (part.strip() for part in raw_value.split(",")):
        if not candidate:
            continue
        cidrs.append(ip_network(candidate, strict=False))
    return tuple(cidrs)


def _parse_ip(value: str | None) -> IpAddress | None:
    if not value:
        return None
    try:
        parsed = ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(parsed, (IPv4Address, IPv6Address)):
        return parsed
    return None


def _is_trusted_proxy(ip_value: IpAddress, trusted_proxy_networks: tuple[TrustedProxyNetwork, ...]) -> bool:
    return any(ip_value in network for network in trusted_proxy_networks)


def _extract_device_ip_with_trust(request: Request, *, trusted_proxy_networks: tuple[TrustedProxyNetwork, ...]) -> str:
    remote_host = request.client.host if request.client and request.client.host else None
    remote_ip = _parse_ip(remote_host)
    if remote_ip is None:
        return (remote_host or "unknown")[:128]

    if not trusted_proxy_networks or not _is_trusted_proxy(remote_ip, trusted_proxy_networks):
        return str(remote_ip)

    forwarded_for = request.headers.get("x-forwarded-for", "")
    hops: list[IpAddress] = []
    for item in forwarded_for.split(","):
        hop = _parse_ip(item)
        if hop:
            hops.append(hop)
    hops.append(remote_ip)

    for hop in reversed(hops):
        if not _is_trusted_proxy(hop, trusted_proxy_networks):
            return str(hop)

    return str(hops[0]) if hops else str(remote_ip)


def extract_device_ip(request: Request, *, trusted_proxy_networks: tuple[TrustedProxyNetwork, ...] = ()) -> str:
    return _extract_device_ip_with_trust(request, trusted_proxy_networks=trusted_proxy_networks)


def current_window_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(second=0, microsecond=0)


def _prune_old_windows(
    db: Session,
    *,
    scope_type: str,
    scope_key: str,
    min_window_start: datetime,
) -> None:
    db.execute(
        delete(ApiRateLimitBucket)
        .where(
            ApiRateLimitBucket.scope_type == scope_type,
            ApiRateLimitBucket.scope_key == scope_key,
            ApiRateLimitBucket.window_start < min_window_start,
        )
        .execution_options(synchronize_session=False)
    )


def _consume_scope(
    db: Session,
    *,
    scope_type: str,
    scope_key: str,
    limit: int,
    now: datetime,
) -> RateLimitSnapshot:
    window_start = current_window_start(now)
    reset_at = window_start + timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    prune_before = window_start - timedelta(minutes=2)

    for _ in range(2):
        row = db.scalar(
            select(ApiRateLimitBucket)
            .where(
                ApiRateLimitBucket.scope_type == scope_type,
                ApiRateLimitBucket.scope_key == scope_key,
                ApiRateLimitBucket.window_start == window_start,
            )
            .with_for_update()
        )

        if row is None:
            row = ApiRateLimitBucket(
                scope_type=scope_type,
                scope_key=scope_key,
                window_start=window_start,
                request_count=1,
                updated_at=now,
            )
            db.add(row)
            try:
                _prune_old_windows(db, scope_type=scope_type, scope_key=scope_key, min_window_start=prune_before)
                db.commit()
            except IntegrityError:
                db.rollback()
                continue

            return RateLimitSnapshot(
                scope=scope_type,
                limit=limit,
                remaining=max(0, limit - 1),
                reset_at=reset_at,
                exceeded=False,
            )

        if row.request_count >= limit:
            return RateLimitSnapshot(
                scope=scope_type,
                limit=limit,
                remaining=0,
                reset_at=reset_at,
                exceeded=True,
            )

        row.request_count += 1
        row.updated_at = now
        db.add(row)
        _prune_old_windows(db, scope_type=scope_type, scope_key=scope_key, min_window_start=prune_before)
        db.commit()

        return RateLimitSnapshot(
            scope=scope_type,
            limit=limit,
            remaining=max(0, limit - row.request_count),
            reset_at=reset_at,
            exceeded=False,
        )

    # If upsert races repeatedly, fail closed for safety.
    return RateLimitSnapshot(
        scope=scope_type,
        limit=limit,
        remaining=0,
        reset_at=reset_at,
        exceeded=True,
    )


def enforce_rate_limits(
    db: Session,
    *,
    now: datetime,
    ip_address: str,
    ip_limit: int,
    user_id: str | None,
    user_limit: int,
) -> RateLimitEvaluation:
    ip_snapshot = _consume_scope(
        db,
        scope_type="ip",
        scope_key=ip_address,
        limit=ip_limit,
        now=now,
    )
    if ip_snapshot.exceeded:
        return RateLimitEvaluation(ip=ip_snapshot, user=None, exceeded_scope="ip")

    user_snapshot: RateLimitSnapshot | None = None
    if user_id:
        user_snapshot = _consume_scope(
            db,
            scope_type="user",
            scope_key=user_id,
            limit=user_limit,
            now=now,
        )
        if user_snapshot.exceeded:
            return RateLimitEvaluation(ip=ip_snapshot, user=user_snapshot, exceeded_scope="user")

    return RateLimitEvaluation(ip=ip_snapshot, user=user_snapshot, exceeded_scope=None)


def retry_after_seconds(snapshot: RateLimitSnapshot, now: datetime) -> int:
    return max(1, int((snapshot.reset_at - now).total_seconds()))
