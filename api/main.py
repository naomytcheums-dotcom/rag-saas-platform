"""
Entry point: `uvicorn api.main:app --reload` (dev) or the Dockerfile's
production command. Everything under Partie 1.1 (authentication) is wired
here; later parts (multi-tenant, billing, ...) add more routers to this
same app rather than starting a second one.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from api.config import settings
from api.database import engine
from api.routers import account, auth, oauth, password, sessions, two_factor, verify
from api.security.rate_limit import is_redis_reachable

app = FastAPI(title="RAG SaaS Platform API", version="0.1.0")

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

app.include_router(auth.router)
app.include_router(password.router)
app.include_router(verify.router)
app.include_router(oauth.router)
app.include_router(two_factor.router)
app.include_router(sessions.router)
app.include_router(account.router)


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
