"""1.1.9 -- list/revoke active sessions (device, IP, last_seen)."""

import datetime as dt
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.session import Session
from api.models.user import User
from api.schemas.auth import MessageResponse
from api.schemas.user import SessionResponse
from api.security.csrf import clear_csrf_cookie
from api.security.hashing import hash_token
from api.security.sessions import clear_refresh_cookie, revoke_session

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    "Where am I logged in?" -- every still-active (not revoked, not
    expired) session/device for the current user, newest-active first.
    Each one is flagged is_current by comparing its stored token hash
    against the caller's own refresh cookie, so the frontend can show
    "this device" distinctly from the others in the list.
    """
    now = dt.datetime.now(dt.timezone.utc)
    result = await db.scalars(
        select(Session)
        .where(Session.user_id == current_user.id, Session.revoked_at.is_(None), Session.expires_at > now)
        .order_by(Session.last_seen_at.desc())
    )
    current_hash = hash_token(refresh_token) if refresh_token else None
    return [
        SessionResponse(
            id=s.id,
            device_info=s.device_info,
            ip_address=s.ip_address,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            is_current=(s.refresh_token_hash == current_hash),
        )
        for s in result
    ]


@router.delete("/{session_id}", response_model=MessageResponse)
async def revoke_session_by_id(
    session_id: uuid.UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    "Log out that other device" (1.1.9) -- e.g. a device you don't
    recognize in the session list, 1.1.15's "suspicious activity"
    scenario. Ownership is checked (a session belonging to a different
    user returns 404, not 403, so this endpoint doesn't even confirm
    whether that session id exists at all to someone probing it).
    revoke_session() (api/security/sessions.py) revokes the refresh token
    AND blacklists the access token minted alongside it, so the
    unrecognized device is locked out immediately -- not just once its
    access token would have expired on its own. If the session being
    revoked happens to be the caller's own current one, its cookies are
    cleared too, so the browser doesn't keep sending now-dead ones.
    """
    session = await db.get(Session, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await revoke_session(db, session)
    await db.commit()

    if refresh_token and hash_token(refresh_token) == session.refresh_token_hash:
        clear_refresh_cookie(response)
        clear_csrf_cookie(response)

    return MessageResponse(message="Session revoked")
