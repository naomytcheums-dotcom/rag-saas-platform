"""
Partie 11.3 -- platform-admin user management. Reuses real, existing
machinery rather than duplicating it: `create_and_send_password_reset`
(the same real email flow a user's own "forgot password" link uses --
an admin triggering this does NOT know or set the new password itself,
same real security property), `revoke_session`/`revoke_all_sessions_for_user`
(the same real session-kill machinery `DELETE /sessions/{id}` uses).
"""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.session import Session
from api.models.user import User


class UserAdminError(Exception):
    pass


class UserNotFoundError(UserAdminError):
    pass


async def list_users_admin(db: AsyncSession, *, limit: int = 20, offset: int = 0, search: str | None = None, is_active: bool | None = None) -> tuple[list[User], int]:
    filters = []
    if search:
        filters.append(User.email.ilike(f"%{search}%"))
    if is_active is not None:
        filters.append(User.is_active == is_active)
    total = await db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    rows = list((await db.scalars(select(User).where(*filters).order_by(User.created_at.desc()).limit(limit).offset(offset))).all())
    return rows, total


async def get_user_admin(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFoundError(str(user_id))
    return user


async def update_user_admin(db: AsyncSession, user_id: uuid.UUID, *, full_name: str | None = None, company: str | None = None) -> User:
    user = await get_user_admin(db, user_id)
    if full_name is not None:
        user.full_name = full_name
    if company is not None:
        user.company = company
    await db.flush()
    return user


async def suspend_user(db: AsyncSession, user_id: uuid.UUID, *, reason: str | None) -> User:
    user = await get_user_admin(db, user_id)
    user.is_active = False
    user.suspended_at = dt.datetime.now(dt.timezone.utc)
    user.suspended_reason = reason
    await db.flush()

    from api.security.sessions import revoke_all_sessions_for_user

    await revoke_all_sessions_for_user(db, user_id)
    return user


async def activate_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await get_user_admin(db, user_id)
    user.is_active = True
    user.suspended_at = None
    user.suspended_reason = None
    await db.flush()
    return user


async def verify_user_email_admin(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await get_user_admin(db, user_id)
    user.is_email_verified = True
    await db.flush()
    return user


async def get_user_sessions_admin(db: AsyncSession, user_id: uuid.UUID) -> list[Session]:
    return list((await db.scalars(select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None)))).all())


async def terminate_user_session_admin(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
    session = await db.scalar(select(Session).where(Session.id == session_id, Session.user_id == user_id))
    if session is None:
        return False

    from api.security.sessions import revoke_session

    await revoke_session(db, session)
    return True
