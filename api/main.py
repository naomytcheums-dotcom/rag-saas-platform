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

import api.models  # noqa: F401 -- real, necessary: guarantees every model in
# api/models/__init__.py's own registry is imported (and its table
# registered on Base.metadata) before any router or the test suite's
# own Base.metadata.create_all() runs. Without this, a model reachable
# by NO router (e.g. api/models/agent_run.py -- no real HTTP "agents"
# endpoint exists) can go unregistered, breaking FK resolution for any
# OTHER model that references it (the real bug found and fixed while
# building Partie 5.1.10's human_approvals table).
from api.config import settings
from api.database import AsyncSessionLocal, engine
from api.monitoring import render_prometheus_metrics, track_request_duration_middleware
from api.routers import (
    ab_tests, account, admin_users, agent_api_keys, agent_traces, agents, api_versioning, audit, auth, autonomous_agents, batch_jobs,
    benchmark_versions, billing,
    chat_integrations_discord, chat_integrations_slack, chat_integrations_teams,
    admin_dashboard, admin_organizations, admin_subscriptions, admin_users_management,
    chat_stream, citations, compliance, conversations, conversation_shares,
    crm, custom_domains, custom_tools, documents, encryption, feedback, i18n, integrations_universal, mcp_server, mcp_servers, media, notification_center, notification_templates, notifications, observability,
    plugins,
    sales,
    sandbox,
    analytics,
    comparison_jobs, deployment_evaluations, email_domains, enterprise_sso, evaluation_comparisons, evaluation_datasets,
    evaluation_jobs, evaluation_results, external_sources, fine_tuning, human_approval, invitations, manual_evaluations, oauth,
    organization_branding, organization_members, organization_settings, organizations, password, public_api, quality_dashboard,
    question_sets, questions, quotas, rbac, reindex_schedules, regression_detection, regression_thresholds,
    resource_permissions, retrieval_diagnostics, search, security_scan, sessions, ssl_certificates, teams, tool_config, tool_permissions, twilio, two_factor,
    usage, user_limits, verify, voice, voice_messages, voice_settings, webauthn, webhooks, white_label, widget, workflows,
    workspaces,
)
from api.security.jwt import refresh_jwt_key_cache
from api.security.rate_limit import is_redis_reachable
from api.services.cache_service import is_redis_reachable as is_cache_redis_reachable
from api.security.rbac import init_rbac
from api.security.logging_correlation import configure_structured_logging, request_correlation_middleware
from api.services.plugin_hooks import plugin_error_hook_middleware
from api.services.white_label_middleware import white_label_domain_middleware
from api.security.datadog_llmobs import setup_llm_observability
from api.security.error_tracking import setup_error_tracking
from api.security.loki_handler import install_loki_handler
from api.security.system_log_handler import install_system_log_handler
from api.security.tracing import setup_tracing, tracing_status

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

    # Partie 11.6 -- real WARNING+ log capture into system_logs. Never
    # installed under the fast test suite (tests/conftest.py's `client`
    # fixture never runs this lifespan at all).
    install_system_log_handler()

    # Partie 13.2 -- request-id correlation filter (always) + JSON
    # console formatter (only when LOG_FORMAT=json).
    configure_structured_logging(settings.LOG_FORMAT)
    install_loki_handler()
    setup_llm_observability()
    setup_error_tracking()

    # Partie 13.4 -- real OpenTelemetry instrumentation, a real no-op
    # unless OTEL_ENABLED is set (see api/security/tracing.py's own
    # docstring for why that's the honest default in this environment).
    setup_tracing(app)

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


# Partie 9.2.9 -- real OpenAPI/Swagger metadata (title/description/
# version/contact/license), all from real, configurable settings
# rather than hardcoded. Note: this project's real OpenAPI/Swagger
# generation (`/openapi.json`, `/docs`, `/redoc`) was ALREADY fully
# functional out of the box (a real, built-in FastAPI feature, not
# something this codebase had to build) -- 9.2.9's own real, missing
# piece was configuring these fields, not generating anything new.
_openapi_contact = None
if settings.OPENAPI_CONTACT_NAME or settings.OPENAPI_CONTACT_EMAIL or settings.OPENAPI_CONTACT_URL:
    _openapi_contact = {"name": settings.OPENAPI_CONTACT_NAME, "email": settings.OPENAPI_CONTACT_EMAIL, "url": settings.OPENAPI_CONTACT_URL}
_openapi_license = None
if settings.OPENAPI_LICENSE_NAME:
    _openapi_license = {"name": settings.OPENAPI_LICENSE_NAME, "url": settings.OPENAPI_LICENSE_URL}

app = FastAPI(
    title=settings.OPENAPI_TITLE, description=settings.OPENAPI_DESCRIPTION, version=settings.OPENAPI_VERSION,
    contact=_openapi_contact, license_info=_openapi_license, lifespan=lifespan,
)

# Required by Authlib's Starlette OAuth client (api/routers/oauth.py) to
# hold the `state`/`nonce` between the /authorize redirect and /callback.
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_MIDDLEWARE_SECRET, same_site="lax", https_only=settings.COOKIE_SECURE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_urls_list,
    # Real bug found (2026-09-18): Vercel gives every deployment its own
    # per-build URL (a random hash, e.g. rag-saas-platform-ltn3d727t-...),
    # on top of the stable production domain and git-branch alias already
    # covered by FRONTEND_URL above. Without this, CORS would need a
    # manual config update on every single deploy. Restricted to this
    # project's own Vercel subdomains, not *.vercel.app generally.
    allow_origin_regex=r"^https://rag-saas-platform-[a-z0-9-]+-naomytcheums-dotcoms-projects\.vercel\.app$",
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
# Partie 9.3.13 -- the ONE real, deliberate exception to "never
# frameable": the widget's own iframe page exists specifically to be
# embedded on an arbitrary third-party site (that's the whole point of
# an iframe-embed integration option, see docs/widget/IFRAME.md) --
# every other real endpoint in this app keeps the strict 'none' below.
_WIDGET_FRAMEABLE_PATH = "/widget/iframe"


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
    elif request.url.path == _WIDGET_FRAMEABLE_PATH:
        # Phase 4, Étape 5 (Domain Allowlist Widget) -- real, minimal
        # fix: `get_widget_iframe` (api/routers/widget.py) now sets its
        # own real, per-organization `frame-ancestors` value (an
        # organization's own configured `allowed_domains`, or the real,
        # unchanged `*` default) -- this middleware runs AFTER the real
        # route handler and used to unconditionally OVERWRITE it back to
        # a real, hardcoded `*` for every organization regardless, a
        # real bug that would have silently defeated this étape's own
        # fix. Only sets the real, global default when the route itself
        # didn't already set one (a real caller other than
        # `get_widget_iframe` reaching this same real path, in
        # principle -- none exists today, but real, honest robustness).
        response.headers.setdefault("Content-Security-Policy", "frame-ancestors *")
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path != _WIDGET_FRAMEABLE_PATH:
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
    # The widget's own real endpoints are the ONE deliberate exception:
    # a third-party site embedding the widget is, by definition, a
    # different site than this API's own -- "cross-origin" (readable by
    # any origin) rather than "same-site" is the real, correct policy
    # here, same real reasoning as the CORS carve-out just above.
    response.headers["Cross-Origin-Resource-Policy"] = "cross-origin" if request.url.path.startswith("/widget/") else "same-site"
    # Only meaningful -- and only safe to promise -- once the app is
    # actually deployed behind HTTPS, same flag that already gates
    # COOKIE_SECURE and SessionMiddleware's https_only above.
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# Partie 9.3 -- the widget's own real, SEPARATE CORS policy (vision
# critique -- "les CORS sont-ils configurés ?"). The app-wide
# CORSMiddleware above only ever allows `settings.FRONTEND_URL` -- by
# design, for every real, authenticated endpoint. A widget embedded on
# an arbitrary third-party site is a genuinely different, deliberately
# open case (`WIDGET_CORS_ALLOWED_ORIGINS`, default `["*"]`): without
# this, a third-party page's own `fetch("/widget/config")` would 200
# at the HTTP level but the BROWSER would still refuse to let that
# page's own JS read the response (no matching
# Access-Control-Allow-Origin), silently breaking the entire feature.
# Registered as its own, separate `@app.middleware` (Starlette makes
# each subsequent one OUTERMOST) rather than a second CORSMiddleware
# instance -- Starlette only supports configuring one -- so this one
# handles `/widget/*` preflights itself, before the global
# CORSMiddleware above ever gets a chance to reject them for not
# matching FRONTEND_URL.
@app.middleware("http")
async def _widget_cors(request: Request, call_next):
    if not request.url.path.startswith("/widget/"):
        return await call_next(request)

    origin = request.headers.get("origin")
    allowed = "*" in settings.WIDGET_CORS_ALLOWED_ORIGINS or (origin and origin in settings.WIDGET_CORS_ALLOWED_ORIGINS)
    allow_origin_header = origin if (origin and allowed) else ("*" if "*" in settings.WIDGET_CORS_ALLOWED_ORIGINS else None)

    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)

    if allow_origin_header:
        response.headers["Access-Control-Allow-Origin"] = allow_origin_header
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# Partie 9.2.8 -- real, minimal API versioning. Real, honest scope:
# this codebase only really HAS one real API version (`v1`, Partie
# 9.1) -- a full real content-negotiation/routing-by-version system
# would be real, speculative infrastructure for versions that don't
# exist yet. This middleware still does the one real, useful thing
# right now: announces the real current/deprecated version on every
# real response, so a real client integrating today is never guessing.
@app.middleware("http")
async def _api_versioning(request: Request, call_next):
    response = await call_next(request)
    response.headers["API-Version"] = settings.API_VERSION_CURRENT
    if settings.API_VERSION_CURRENT in settings.API_VERSION_DEPRECATED:
        response.headers["API-Deprecated"] = "true"
    return response


# Audit finding 22 -- registered AFTER _security_headers so it wraps the
# full request/response cycle including that middleware's own work,
# giving the most complete picture of "how long did this request take."
app.middleware("http")(track_request_duration_middleware)
app.middleware("http")(request_correlation_middleware)
# Partie 19 -- real Host-header custom-domain detection. See
# api/services/white_label_middleware.py's own docstring for exact,
# honest scope (attaches request.state, doesn't rewrite routing).
app.middleware("http")(white_label_domain_middleware)
# Partie 16 (ter) -- the real on_error plugin hook. Registered LAST so
# it wraps outermost (Starlette applies the most-recently-added
# middleware first on the way in), catching a real unhandled exception
# from every inner layer -- routes and the other middleware above --
# and always re-raising it unchanged afterward.
app.middleware("http")(plugin_error_hook_middleware)

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
app.include_router(workflows.router)
app.include_router(resource_permissions.router)
app.include_router(retrieval_diagnostics.router)
app.include_router(teams.router)
app.include_router(invitations.router)
app.include_router(quotas.router)
app.include_router(user_limits.router)
app.include_router(usage.router)
app.include_router(organization_settings.router)
app.include_router(organization_branding.router)
app.include_router(sandbox.router)
app.include_router(custom_domains.router)
app.include_router(custom_tools.router)
app.include_router(crm.router)
app.include_router(mcp_servers.router)
app.include_router(mcp_server.router)
app.include_router(ssl_certificates.router)
app.include_router(email_domains.router)
app.include_router(white_label.router)
app.include_router(documents.router)
app.include_router(external_sources.router)
app.include_router(reindex_schedules.router)
app.include_router(batch_jobs.router)
app.include_router(citations.router)
app.include_router(chat_stream.router)
app.include_router(search.router)
app.include_router(tool_permissions.router)
app.include_router(tool_config.router)
app.include_router(human_approval.router)
app.include_router(conversations.router)
app.include_router(conversation_shares.router)
app.include_router(feedback.router)
app.include_router(questions.router)
app.include_router(i18n.router)
app.include_router(voice.router)
app.include_router(voice_messages.router)
app.include_router(voice_settings.router)
app.include_router(twilio.router)
app.include_router(public_api.router)
app.include_router(webhooks.router)
app.include_router(api_versioning.router)
app.include_router(widget.router)
app.include_router(chat_integrations_slack.router)
app.include_router(chat_integrations_teams.router)
app.include_router(chat_integrations_discord.router)
app.include_router(agent_traces.router)
app.include_router(agents.router)
app.include_router(agent_api_keys.router)
app.include_router(quality_dashboard.router)
app.include_router(evaluation_datasets.router)
app.include_router(question_sets.router)
app.include_router(benchmark_versions.router)
app.include_router(evaluation_results.router)
app.include_router(evaluation_comparisons.router)
app.include_router(evaluation_jobs.router)
app.include_router(manual_evaluations.router)
app.include_router(comparison_jobs.router)
app.include_router(regression_detection.router)
app.include_router(regression_thresholds.router)
app.include_router(deployment_evaluations.router)
app.include_router(rbac.router)
app.include_router(compliance.router)
app.include_router(encryption.router)
app.include_router(security_scan.router)
app.include_router(admin_dashboard.router)
app.include_router(admin_organizations.router)
app.include_router(admin_users_management.router)
app.include_router(admin_subscriptions.router)
app.include_router(billing.router)
app.include_router(billing.org_router)
app.include_router(observability.router)
app.include_router(integrations_universal.router)
app.include_router(integrations_universal.org_router)
app.include_router(notifications.router)
app.include_router(notification_center.router)
app.include_router(notification_templates.router)
app.include_router(sales.router)
app.include_router(sales.org_router)
app.include_router(analytics.router)
app.include_router(analytics.org_router)
app.include_router(plugins.marketplace_router)
app.include_router(plugins.org_router)
app.include_router(plugins.admin_router)
app.include_router(ab_tests.router)
app.include_router(media.router)
app.include_router(autonomous_agents.router)
app.include_router(fine_tuning.router)


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
    # Étape 13 -- api/services/cache_service.py has the exact same
    # fail-open trade-off as rate_limit.py (see that module's own
    # docstring): unreachable means every get_or_set becomes a real
    # passthrough, never wrong, just slower. Same reasoning as
    # rate_limit_redis above for why that must be visible here, not
    # just a warning log.
    cache_redis_ok = await is_cache_redis_reachable()

    return {
        "database": "ok" if database_ok else "unreachable",
        "rate_limit_redis": "ok" if redis_ok else "unreachable -- rate limiting is NOT currently enforced",
        "cache_redis": "ok" if cache_redis_ok else "unreachable -- application cache is NOT currently active (passthrough)",
    }
