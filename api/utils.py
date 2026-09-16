"""Small cross-cutting helpers with no single obvious home."""

import datetime as dt

from fastapi import Request

# Coherence fix (audit finding, 2026-09-16): the same `200` pagination
# ceiling used to be redefined independently as a private
# `_MAX_PAGE_SIZE` module constant in 3 separate routers
# (audit.py, quality_dashboard.py, usage.py) -- same value everywhere,
# but nothing actually tied them together, so a future change to one
# could silently drift from the others. One shared constant instead.
MAX_PAGE_SIZE = 200


def client_ip(request: Request) -> str | None:
    """
    Best-effort caller IP -- used both to display in the sessions list
    (api/routers/sessions.py) and as a rate-limiting key
    (api/security/rate_limit.py). Prefers X-Forwarded-For's first entry
    (the original client, when running behind a reverse proxy/load
    balancer) and falls back to the direct connection's address.

    Security caveat, worth being explicit about: this trusts
    X-Forwarded-For at face value. That's correct and necessary when
    deployed behind a real reverse proxy/load balancer that sets/overwrites
    this header itself (Render, Fly.io, and most PaaS do) -- but if this
    app is ever exposed directly to the internet with no such proxy in
    front of it, any client can set an arbitrary X-Forwarded-For value
    and trivially defeat IP-based rate limiting. Deploying behind a
    trusted proxy is what makes this header trustworthy, not anything in
    this function.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def as_aware_utc(value: dt.datetime) -> dt.datetime:
    """Postgres round-trips a DateTime(timezone=True) column back as
    tz-aware; SQLite (used in tests, see tests/conftest.py) does not -- a
    value written aware comes back naive. Every datetime this app ever
    writes is already UTC (dt.datetime.now(dt.timezone.utc), called
    directly at each call site), so treating a naive value as UTC on
    read is a correct normalization, not a guess."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)
