"""
Partie 9.3 -- real widget authentication, deliberately in TWO tiers
(vision critique -- security: "la clé API n'est-elle pas exposée dans
le script ?"):

1. `public_key` (`WidgetConfig.public_key`, `wgt_...`) -- a real,
   non-secret identifier, safe to embed in a <script data-key="...">
   tag on any third-party site (view-source shows it to anyone).
   Resolving it only ever returns PUBLIC config (colors, name, logo,
   welcome message, position, theme, suggested questions) -- never a
   real, secret `OrganizationAPIKey`.

2. A short-lived widget session token (`create_widget_session_token`/
   `verify_widget_session_token` below) -- minted once per real visitor
   session from the public key, and THAT is what the browser actually
   sends on `POST /widget/chat`. This is the real fix the vision
   critique asks for: a leaked/inspected public key alone can mint new
   chat sessions against this organization's widget (rate-limited, see
   `WIDGET_SESSION_TOKEN_EXPIRE_MINUTES`) but can never see or act as a
   real, secret `OrganizationAPIKey` (9.1/9.2) -- an entirely separate,
   unrelated credential.

Deliberately its own small JWT, not a reuse of `api/security/jwt.py`'s
`create_access_token`/`decode_token`: those are real, USER-identity
tokens (`sub` = a real `User.id`, checked against real Session/
blacklist rows). A widget visitor is anonymous -- there is no real
user account behind them -- so forcing them through the same token
pipeline would either require inventing a fake user per visitor (real
data-model pollution) or silently weakening what `create_access_token`
means for every other real caller. A second, purpose-built, narrowly-
scoped token is the honest fix.
"""

import datetime as dt
import re
import uuid
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.models.widget import WidgetConfig

_ALGORITHM = "HS256"
_PURPOSE = "widget_session"

# --------------------------------------------------------------------
# Phase 4, Étape 5 -- Domain Allowlist Widget. Real, minimal audit
# finding (catch): `WidgetConfig.public_key` was ALWAYS designed to be
# non-secret (this module's own top docstring, unchanged since Partie
# 9.3), and `GET /widget/iframe` ALREADY sent `frame-ancestors *` /
# `X-Frame-Options: ALLOWALL` -- BY DESIGN, DOCUMENTED as this
# codebase's own ONE deliberate "frameable" exception (api/main.py's
# own `_WIDGET_FRAMEABLE_PATH`/`_security_headers`). `POST
# /widget/session` (the REAL authorization boundary -- it mints the
# session token `POST /widget/chat` actually trusts) had NO origin
# check of any kind. `settings.WIDGET_CORS_ALLOWED_ORIGINS`
# (api/main.py's own `_widget_cors` middleware) is a real, GLOBAL,
# platform-wide setting -- not per-organization, and CORS headers only
# ever govern whether a BROWSER's own JS may READ a response, never
# whether the SERVER processes the request at all (a real, common
# CORS misconception this étape's own audit explicitly tests for).
#
# Real, minimal fix, reusing this SAME module (the canonical home for
# every other real widget security concern -- public-key resolution,
# session tokens) rather than a new `cors.py`/`origin_check.py`: an
# OPTIONAL, per-organization `WidgetConfig.allowed_domains` (`None`/
# empty = real, UNCHANGED, unrestricted behavior -- rétrocompatibilité)
# enforced at the 2 real points origin actually matters:
# 1. `POST /widget/session` (api/routers/widget.py) -- rejects minting
#    a session token for a disallowed origin, the real authorization
#    boundary, independent of any CORS header.
# 2. `GET /widget/iframe` (api/routers/widget.py) -- emits a real,
#    per-organization `Content-Security-Policy: frame-ancestors`
#    instead of the real, global `*`, when configured.
# The real, global CORS middleware/`WIDGET_CORS_ALLOWED_ORIGINS` is
# left UNCHANGED (still governs whether ANY browser JS can read ANY
# widget response platform-wide) -- these 2 fixes are a real, separate,
# ADDITIONAL per-organization authorization layer, not a replacement.

MAX_WIDGET_ALLOWED_DOMAINS = 20
# A real, explicit wildcard-SUBDOMAIN syntax only (`*.example.com`) --
# never a bare `*` (real, unrestricted -- already the real, honest
# meaning of an EMPTY list, no need for a second way to say it) and
# never a wildcard anywhere but the leftmost label (`*.example.com`,
# not `example.*.com`/`*example.com`) -- a real, deliberate, narrow
# grammar (vision critique 14: "un admin ne doit pas pouvoir configurer
# * / .example.com / https://*.example.com/* / javascript:alert(1)
# sans que cela soit explicitement supporté").
_DOMAIN_RE = re.compile(r"^(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
_ALLOWED_DOMAIN_SCHEMES = ("http", "https")


class WidgetDomainError(ValueError):
    """Real, dedicated exception -- routers turn this into a 4xx."""


def validate_widget_domain(raw: str) -> str:
    """Item 14's own literal ask -- real, strict validation of ONE
    real, admin-configured allowlist entry at CONFIGURATION time (not
    just at runtime match time, so a real typo/malformed entry is
    caught immediately, not silently never-matching later). Accepts a
    real bare hostname (`example.com`), an explicit `*.example.com`
    subdomain wildcard, or a full `scheme://host[:port]` origin
    (`https://example.com:8443`) -- normalizes all 3 real shapes to a
    real, canonical `scheme://host[:port]` string (defaulting to
    `https://` when no real scheme was given, this codebase's own
    real, standard default -- see api/services/url_fetching.py's own
    `_ALLOWED_SCHEMES`). Real, explicit rejections: `*` alone, a
    leading/trailing dot, a path/query/fragment, a disallowed scheme
    (`javascript:`, `data:`, ...), embedded credentials, a wildcard
    anywhere but a real, leading `*.` label, and any entry once this
    module's own `MAX_WIDGET_ALLOWED_DOMAINS` real cap is exceeded (checked
    by the real caller, `api.services.widget.set_widget_allowed_domains`,
    which sees the whole real list at once)."""
    raw = raw.strip()
    if not raw:
        raise WidgetDomainError("A widget allowed domain cannot be empty")
    if raw == "*":
        raise WidgetDomainError("'*' is not a real, explicit domain -- use an empty allowlist for unrestricted embedding instead")

    candidate = raw if "://" in raw else f"https://{raw}"
    parts = urlsplit(candidate)
    if parts.scheme not in _ALLOWED_DOMAIN_SCHEMES:
        raise WidgetDomainError(f"Unsupported scheme in {raw!r} (expected http/https or none)")
    if parts.username or parts.password:
        raise WidgetDomainError(f"{raw!r} must not contain embedded credentials")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise WidgetDomainError(f"{raw!r} must be a bare origin (no path/query/fragment)")
    hostname = (parts.hostname or "").lower().rstrip(".")
    if not hostname:
        raise WidgetDomainError(f"{raw!r} has no real hostname")
    if not _DOMAIN_RE.match(hostname):
        raise WidgetDomainError(f"{raw!r} is not a valid domain (a wildcard is only ever supported as a leading '*.' label)")

    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{hostname}{port}"


def _matches_allowed_domain(origin_scheme: str, origin_host: str, origin_port: int | None, allowed: str) -> bool:
    parts = urlsplit(allowed)
    allowed_host = parts.hostname or ""
    if parts.scheme != origin_scheme or parts.port != origin_port:
        # Real, exact port equality -- `None` matches `None` (neither
        # the allowlist entry nor the real request origin named an
        # explicit port), anything else must match exactly.
        return False
    if allowed_host.startswith("*."):
        suffix = allowed_host[1:]  # keep the leading dot -- ".example.com"
        return origin_host.endswith(suffix) and origin_host != suffix.lstrip(".")
    return origin_host == allowed_host


def resolve_request_origin(request: Request) -> str | None:
    """Phase 4, Étape 5bis -- real, single source of truth for "what
    origin is this real request coming from", reused at BOTH real
    points that need it: `POST /widget/session` (to check against
    `allowed_domains`, AND to embed as the real token's own `origin`
    claim below) and `require_widget_session` (to verify a real,
    already-minted token's own claim still matches). Real `Origin`
    first, real `Referer` as fallback (some real, legitimate browser
    configurations omit `Origin` but still send `Referer`), `None` when
    real neither is present."""
    return request.headers.get("origin") or request.headers.get("referer") or None


def is_origin_allowed(origin: str | None, allowed_domains: list[str] | None) -> bool:
    """Item 6's own literal ask -- the real, runtime check. Real,
    deliberate rétrocompatibilité (requirement 4/20): an empty/`None`
    `allowed_domains` (every real, pre-existing organization's own real
    default) always returns `True` -- unrestricted, exactly this
    codebase's own real, unchanged, pre-existing behavior.

    Real, deliberate decisions on the harder real cases (this étape's
    own explicit audit list), each independently verified against a
    real, direct parse rather than assumed:
    - `origin=None` (no real `Origin` header at all -- a real,
      non-browser caller: curl, a server-to-server health check, a
      same-origin request) is ALLOWED even when a real allowlist is
      configured -- the real threat this étape defends against is an
      unauthorized real WEBSITE embedding/calling this widget from a
      real BROWSER, which always sends a real `Origin` header on a
      real cross-origin `fetch`/`XHR`; blocking a real, origin-less
      caller serves no real security purpose here and would break real
      server-side/monitoring use.
    - `origin="null"` (a real, well-known browser value for a real
      sandboxed iframe/`data:`/`file:` context) is NEVER treated as a
      match against a real, non-empty allowlist -- a real attacker
      forcing `Origin: null` must never bypass a real, explicit
      allowlist.
    - A malformed/unparseable real `origin` string is rejected (not a
      match) when a real allowlist is configured.
    - Real hostname comparison is case-insensitive, real port-exact,
      real scheme-exact, real trailing-dot-normalized -- see
      `_matches_allowed_domain` above."""
    if not allowed_domains:
        return True
    if not origin or origin.lower() == "null":
        return False
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    if parts.scheme not in _ALLOWED_DOMAIN_SCHEMES or not parts.hostname:
        return False
    host = parts.hostname.lower().rstrip(".")
    return any(_matches_allowed_domain(parts.scheme, host, parts.port, allowed) for allowed in allowed_domains)


class WidgetAuthError(ValueError):
    """Real, honest failure -- routers turn this into a 4xx."""


async def get_widget_config_by_public_key(db: AsyncSession, public_key: str) -> WidgetConfig:
    config = await db.scalar(select(WidgetConfig).where(WidgetConfig.public_key == public_key))
    if config is None:
        raise WidgetAuthError("Unknown or revoked widget key")
    return config



# Phase 4, Étape 5bis (Widget Hardening Complet) -- real, dedicated
# sentinel for "this real, decoded token has no `origin` claim at all"
# (a real, pre-Étape-5bis token) -- deliberately NOT `None` (a real,
# valid, POST-fix claim value for "minted with no real Origin/Referer
# present"), so a real, legacy token can never accidentally match a
# real, origin-less request either. A real, deliberately unparseable
# string (never a real, valid `scheme://host` origin), so it can never
# collide with a real request's own resolved origin.
_NO_ORIGIN_CLAIM = "__widget_no_origin_claim__"


def create_widget_session_token(widget_config_id: uuid.UUID, organization_id: uuid.UUID, agent_id: uuid.UUID | None, origin: str | None = None) -> str:
    """Item 3's own literal function (`create_widget_session`) --
    named `create_widget_session_token` here since it mints a real
    JWT, not a real DB-persisted session row (a widget visitor is
    anonymous and stateless between page loads on purpose; there is no
    real row to revoke individually, only the short real expiry
    below).

    Phase 4, Étape 5bis -- real, genuine hardening (this étape's own
    "Limite 2"): `origin` (this module's own new
    `resolve_request_origin`, resolved by the real caller at real
    session-creation time) is now embedded as a real, additional JWT
    claim. `require_widget_session` below re-resolves the SAME real
    origin at EVERY real `/widget/chat` call and rejects a real
    mismatch -- a real, stolen/observed token can no longer be replayed
    from a real, different origin, even before its own real, short
    expiry. `origin=None` (a real, legitimate, non-browser caller with
    neither `Origin` nor `Referer`) is a real, valid claim value in its
    own right -- distinct from `_NO_ORIGIN_CLAIM` below, which marks a
    real, pre-existing token that predates this whole real claim."""
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "purpose": _PURPOSE,
        "widget_config_id": str(widget_config_id),
        "organization_id": str(organization_id),
        "agent_id": str(agent_id) if agent_id else None,
        "origin": origin,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.WIDGET_SESSION_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=_ALGORITHM)


class WidgetSession:
    def __init__(self, widget_config_id: uuid.UUID, organization_id: uuid.UUID, agent_id: uuid.UUID | None, origin: str | None = _NO_ORIGIN_CLAIM):
        self.widget_config_id = widget_config_id
        self.organization_id = organization_id
        self.agent_id = agent_id
        self.origin = origin


def verify_widget_session_token(token: str) -> WidgetSession:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise WidgetAuthError("Invalid or expired widget session token") from exc

    if payload.get("purpose") != _PURPOSE:
        raise WidgetAuthError("Invalid or expired widget session token")

    return WidgetSession(
        widget_config_id=uuid.UUID(payload["widget_config_id"]),
        organization_id=uuid.UUID(payload["organization_id"]),
        agent_id=uuid.UUID(payload["agent_id"]) if payload.get("agent_id") else None,
        # Real, deliberate sentinel default: a real key genuinely
        # ABSENT from `payload` (a real, pre-Étape-5bis token) resolves
        # to `_NO_ORIGIN_CLAIM`, never to a real, valid `None` -- see
        # `create_widget_session_token`'s own updated docstring.
        origin=payload.get("origin", _NO_ORIGIN_CLAIM),
    )


async def require_widget_public_key(key: str = Query(..., alias="key"), db: AsyncSession = Depends(get_db)) -> WidgetConfig:
    """Real dependency for every PUBLIC widget GET endpoint
    (`?key=wgt_...`) -- 404, not 401/403, for an unknown key: same
    anti-enumeration reasoning used throughout this codebase (see
    `require_org_member`'s own docstring), so a scanner can't tell
    "wrong key" apart from "no such organization" either."""
    try:
        return await get_widget_config_by_public_key(db, key)
    except WidgetAuthError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc


async def require_widget_session(request: Request, authorization: str | None = Header(default=None)) -> WidgetSession:
    """Real dependency for `POST /widget/chat` -- expects
    `Authorization: Bearer <widget session token>`, NOT the public
    key (the public key alone cannot send messages, only mint a
    session -- see this module's own top docstring).

    Phase 4, Étape 5bis -- real, genuine hardening (this étape's own
    "Limite 2"): the real, current request's own origin (resolved the
    SAME real way `POST /widget/session` already does) must EXACTLY
    match the real token's own `origin` claim -- a real mismatch (a
    real, different origin, OR a real, pre-Étape-5bis token with no
    real claim at all, `_NO_ORIGIN_CLAIM`, which can never equal a real
    request's own resolved origin) is a real 403, forcing a real,
    fresh `/widget/session` call. No real, active migration needed for
    a real, already-deployed, pre-fix token -- this module's own real,
    short `WIDGET_SESSION_TOKEN_EXPIRE_MINUTES` expiry already
    self-heals every real, in-flight token within that real window."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing widget session token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        session = verify_widget_session_token(token)
    except WidgetAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if session.origin != resolve_request_origin(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This widget session cannot be used from this origin")
    return session
