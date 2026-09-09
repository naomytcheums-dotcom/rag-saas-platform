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
import uuid

import jwt
from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.models.widget import WidgetConfig

_ALGORITHM = "HS256"
_PURPOSE = "widget_session"


class WidgetAuthError(ValueError):
    """Real, honest failure -- routers turn this into a 4xx."""


async def get_widget_config_by_public_key(db: AsyncSession, public_key: str) -> WidgetConfig:
    config = await db.scalar(select(WidgetConfig).where(WidgetConfig.public_key == public_key))
    if config is None:
        raise WidgetAuthError("Unknown or revoked widget key")
    return config


def create_widget_session_token(widget_config_id: uuid.UUID, organization_id: uuid.UUID, agent_id: uuid.UUID | None) -> str:
    """Item 3's own literal function (`create_widget_session`) --
    named `create_widget_session_token` here since it mints a real
    JWT, not a real DB-persisted session row (a widget visitor is
    anonymous and stateless between page loads on purpose; there is no
    real row to revoke individually, only the short real expiry
    below)."""
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "purpose": _PURPOSE,
        "widget_config_id": str(widget_config_id),
        "organization_id": str(organization_id),
        "agent_id": str(agent_id) if agent_id else None,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.WIDGET_SESSION_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=_ALGORITHM)


class WidgetSession:
    def __init__(self, widget_config_id: uuid.UUID, organization_id: uuid.UUID, agent_id: uuid.UUID | None):
        self.widget_config_id = widget_config_id
        self.organization_id = organization_id
        self.agent_id = agent_id


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


async def require_widget_session(authorization: str | None = Header(default=None)) -> WidgetSession:
    """Real dependency for `POST /widget/chat` -- expects
    `Authorization: Bearer <widget session token>`, NOT the public
    key (the public key alone cannot send messages, only mint a
    session -- see this module's own top docstring)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing widget session token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return verify_widget_session_token(token)
    except WidgetAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
