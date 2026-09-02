"""
Audit finding 15 -- reject a new password that matches the CURRENT one or
any of the user's last PASSWORD_HISTORY_SIZE passwords
(api/models/password_history.py). Password hashes are salted bcrypt, so
"matches" can't be a string/hash comparison -- each candidate is checked
with verify_password (bcrypt.checkpw), same as an ordinary login.

Both queries below order by `sequence`, not `created_at` -- see
api/models/password_history.py's own docstring for why: two rows
written in fast succession can share the same microsecond-truncated
timestamp, which made "most recent N rows" genuinely non-deterministic
under real Postgres (confirmed via a flake in real CI). `sequence` is a
monotonic-per-user counter that can never tie, so the reuse-check and
the prune below always agree on exactly which rows count as "recent."
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.password_history import PasswordHistory
from api.security.hashing import verify_password

def _reuse_error() -> HTTPException:
    # A function, not a module-level constant -- the message embeds
    # settings.PASSWORD_HISTORY_SIZE, which must reflect whatever value
    # is current when the error is actually raised (tests override it).
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"This password has been used too recently -- choose one you haven't used in your last {settings.PASSWORD_HISTORY_SIZE} passwords.",
    )


async def reject_if_password_reused(db: AsyncSession, user_id: UUID, new_password: str, current_hashed_password: str | None) -> None:
    """Raises PASSWORD_REUSE_ERROR if `new_password` matches the CURRENT
    password or any of the last PASSWORD_HISTORY_SIZE historical ones.
    current_hashed_password is checked separately from the history table
    (not itself written there until record_password_change() below runs)
    since a user's very first password change would otherwise have no
    history row to catch "new password same as the one being replaced."
    """
    if current_hashed_password is not None and verify_password(new_password, current_hashed_password):
        raise _reuse_error()

    history = (await db.scalars(
        select(PasswordHistory)
        .where(PasswordHistory.user_id == user_id)
        .order_by(PasswordHistory.sequence.desc())
        .limit(settings.PASSWORD_HISTORY_SIZE)
    )).all()
    for row in history:
        if verify_password(new_password, row.password_hash):
            raise _reuse_error()


async def record_password_change(db: AsyncSession, user_id: UUID, new_hashed_password: str) -> None:
    """Called AFTER a password change actually succeeds -- stores the new
    hash and prunes anything beyond the most recent PASSWORD_HISTORY_SIZE
    rows for this user, so the table never grows without bound and stays
    a reuse-check window rather than a permanent log. Caller commits.

    `sequence` is computed here, not DB-assigned (see
    api/models/password_history.py's docstring for why) -- next integer
    per user_id, same "compute in code, let the unique constraint catch
    a genuine collision" shape as generate_unique_slug
    (api/security/organizations.py)."""
    next_sequence = 1 + (await db.scalar(
        select(func.max(PasswordHistory.sequence)).where(PasswordHistory.user_id == user_id)
    ) or 0)
    db.add(PasswordHistory(user_id=user_id, password_hash=new_hashed_password, sequence=next_sequence))
    await db.flush()

    stale_ids = (await db.scalars(
        select(PasswordHistory.id)
        .where(PasswordHistory.user_id == user_id)
        .order_by(PasswordHistory.sequence.desc())
        .offset(settings.PASSWORD_HISTORY_SIZE)
    )).all()
    if stale_ids:
        await db.execute(delete(PasswordHistory).where(PasswordHistory.id.in_(stale_ids)))
