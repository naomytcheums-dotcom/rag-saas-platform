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
from api.security.hashing import hash_token
from api.security.sessions import clear_refresh_cookie, revoke_session

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
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
    session = await db.get(Session, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await revoke_session(db, session)
    await db.commit()

    if refresh_token and hash_token(refresh_token) == session.refresh_token_hash:
        clear_refresh_cookie(response)

    return MessageResponse(message="Session revoked")
