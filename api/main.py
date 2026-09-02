"""
Entry point: `uvicorn api.main:app --reload` (dev) or the Dockerfile's
production command. Everything under Partie 1.1 (authentication) is wired
here; later parts (multi-tenant, billing, ...) add more routers to this
same app rather than starting a second one.
"""

import asyncio
import contextlib
import logging

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from api.config import settings
from api.database import AsyncSessionLocal, engine
from api.monitoring import render_prometheus_metrics, track_request_duration_middleware
from api.routers import (
    account, admin_users, audit, auth, enterprise_sso, oauth, organization_members, organizations, password,
    resource_permissions, sessions, two_factor, verify, webauthn, workspaces,
)
from api.security.jwt import refresh_jwt_key_cache
from api.security.rate_limit import is_redis_reachable
from api.security.rbac import init_rbac

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Audit finding 28: populates api/security/jwt.py's in-memory
    DB-backed-key cache once at startup, then keeps it fresh on a
    JWT_KEY_CACHE_REFRESH_SECONDS timer for the process's whole
    lifetime -- see that module's top docstring for why this timer,
    not a restart, is what makes a Celery-driven rotation "automatic"
    for an already-running process. Cancelled cleanly on shutdown.

    A deployment that never enables JWT_AUTO_ROTATION_INTERVAL_DAYS (the
    default, 0) still runs this loop -- refresh_jwt_key_cache() just
    finds zero rows in jwt_signing_keys forever, leaving the cache empty
    and api/security/jwt.py falling back to JWT_SECRET_KEY exactly as it
    did before this feature existed. The cost is one cheap, indexed
    Postgres query per JWT_KEY_CACHE_REFRESH_SECONDS (60s by default),
    not per request.
    """
    async with AsyncSessionLocal() as db:
        await refresh_jwt_key_cache(db)

    # Etape 1.2.7: loads/seeds the RBAC policy table once, into memory --
    # see api/security/rbac.py's module docstring for why this is a
    # single startup call, not a polling loop like the JWT cache above
    # (policies are static/seeded, not expected to change without a
    # deploy that reseeds them).
    await init_rbac()

    async def _poll_jwt_key_cache() -> None:
        while True:
            await asyncio.sleep(settings.JWT_KEY_CACHE_REFRESH_SECONDS)
            try:
                async with AsyncSessionLocal() as db:
                    await refresh_jwt_key_cache(db)
            except Exception:  # noqa: BLE001 -- a single failed refresh must never kill the polling loop itself
                logger.exception("unexpected error while polling the JWT signing-key cache")

    poll_task = asyncio.create_task(_poll_jwt_key_cache())
    try:
        yield
    finally:
        poll_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poll_task


app = FastAPI(title="RAG SaaS Platform API", version="0.1.0", lifespan=lifespan)

# Required by Authlib's Starlette OAuth client (api/routers/oauth.py) to
# hold the `state`/`nonce` between the /authorize redirect and /callback.
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_MIDDLEWARE_SECRET, same_site="lax", https_only=settings.COOKIE_SECURE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,  # the refresh-token cookie requires this
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1.1-audit finding: no security-header middleware existed at all --
# HSTS/CSP/X-Frame-Options/X-Content-Type-Options/Referrer-Policy were
# entirely absent from every response. Applied as a plain @app.middleware
# rather than a third-party package (same "the logic is short enough to
# read in a few minutes" reasoning as api/security/rate_limit.py) --
# these are five static header assignments, not a library's worth of
# behavior.
_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    # This is a JSON API with no first-party scripts/styles/images of its
    # own -- 'none' is correct everywhere except FastAPI's own built-in
    # Swagger/ReDoc UI, which loads its JS/CSS from a CDN and would
    # simply fail to render under a policy this strict.
    if request.url.path in _DOCS_PATHS:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' cdn.jsdelivr.net 'unsafe-inline'; "
            "style-src 'self' cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' fastapi.tiangolo.com data:; "
            "font-src cdn.jsdelivr.net"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # CI/CD audit finding: OWASP ZAP's real API scan against a live
    # instance flagged this as missing on every response. "same-site"
    # rather than the stricter "same-origin" -- FRONTEND_URL is commonly
    # a different subdomain of the same site (app.example.com calling
    # api.example.com), and CORSMiddleware already governs which origins
    # can actually read a cross-origin response; this only blocks
    # cross-SITE embedding (a different registrable domain), matching
    # the SameSite=lax policy already used on every cookie this app sets.
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    # Only meaningful -- and only safe to promise -- once the app is
    # actually deployed behind HTTPS, same flag that already gates
    # COOKIE_SECURE and SessionMiddleware's https_only above.
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# Audit finding 22 -- registered AFTER _security_headers so it wraps the
# full request/response cycle including that middleware's own work,
# giving the most complete picture of "how long did this request take."
app.middleware("http")(track_request_duration_middleware)

app.include_router(auth.router)
app.include_router(password.router)
app.include_router(verify.router)
app.include_router(oauth.router)
app.include_router(two_factor.router)
app.include_router(sessions.router)
app.include_router(account.router)
app.include_router(audit.router)
app.include_router(webauthn.router)
app.include_router(enterprise_sso.router)
app.include_router(admin_users.router)
app.include_router(organizations.router)
app.include_router(organization_members.router)
app.include_router(workspaces.router)
app.include_router(resource_permissions.router)


@app.get("/metrics", tags=["monitoring"])
async def metrics():
    """
    Audit finding 22 -- Prometheus text exposition format
    (api/monitoring.py), scrapeable directly by a real Prometheus server.
    Correctly aggregates across multiple worker processes when
    PROMETHEUS_MULTIPROC_DIR is set (see gunicorn.conf.py) -- a single
    process reads its own in-memory metrics either way, so nothing about
    running this with one worker (e.g. local dev) needs that variable
    set at all. Deliberately public/unauthenticated, same as /health and
    /health/ready: a metrics scraper generally can't do OAuth, and the
    real access control for this endpoint is expected to be network-level
    (firewalled to the scraper's own network/VPC), not application-level.
    """
    return Response(content=render_prometheus_metrics(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health", tags=["monitoring"])
async def health():
    """Liveness check for load balancers/uptime monitors -- deliberately
    does not touch the database, so it answers even if Postgres is
    temporarily unreachable (a real readiness check that does touch
    dependencies is /health/ready below)."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["monitoring"])
async def readiness():
    """
    Readiness check: unlike /health above, this actually reaches the
    services a request might depend on, so an operator can tell "the
    process is up" apart from "the process can currently do its job
    correctly." Always returns 200 -- the body is what's actionable, not
    the status code, so a degraded dependency here doesn't get treated
    as "take this instance out of the load balancer" by infrastructure
    that only checks status codes; a human or a dashboard is meant to
    read the body.

    rate_limit_redis matters most operationally: api/security/rate_limit.py
    deliberately fails OPEN when Redis is unreachable, meaning brute-force
    protection on login/register/2FA/password-reset/etc. silently stops
    being enforced. That's the right trade-off for availability (see that
    module's docstring), but it must never be a SILENT trade-off -- this
    is how an operator actually finds out it's currently happening,
    instead of only a warning line in a log nobody's tailing.
    """
    database_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    redis_ok = await is_redis_reachable()

    return {
        "database": "ok" if database_ok else "unreachable",
        "rate_limit_redis": "ok" if redis_ok else "unreachable -- rate limiting is NOT currently enforced",
    }
