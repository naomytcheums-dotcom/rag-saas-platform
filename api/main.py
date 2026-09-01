"""
Entry point: `uvicorn api.main:app --reload` (dev) or the Dockerfile's
production command. Everything under Partie 1.1 (authentication) is wired
here; later parts (multi-tenant, billing, ...) add more routers to this
same app rather than starting a second one.
"""

from fastapi import FastAPI, Request
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
    # Only meaningful -- and only safe to promise -- once the app is
    # actually deployed behind HTTPS, same flag that already gates
    # COOKIE_SECURE and SessionMiddleware's https_only above.
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

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
