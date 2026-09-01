"""
1.1.15 -- the access-token blacklist. Access tokens are otherwise
stateless JWTs (api/security/jwt.py): nothing to look up, nothing to
revoke, just a signature and an expiry -- fast, but it means a leaked
token stays valid for up to ACCESS_TOKEN_EXPIRE_MINUTES no matter what
the server does. This table is what makes revocation possible: every row
is one access token's `jti` that must be rejected even though its
signature and expiry are still otherwise fine.

Rows are written by api/security/sessions.py's revoke_session() (and its
bulk counterpart, revoke_all_sessions_for_user()) whenever a session is
revoked -- logout, refresh rotation, password reset, account deletion,
consent withdrawal, 2FA disable, 2FA lockout-recovery, or an explicit
"revoke this session" call. api/dependencies.py's get_current_user checks
every access token against this table on every authenticated request --
see that function's docstring for the trade-off this costs.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class RevokedAccessToken(Base):
    __tablename__ = "revoked_access_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # No FK-cascade cleanup relied on for correctness here: a revoked
    # token must stay rejected even if the user row is later deleted
    # through some path that doesn't go through this table. The FK still
    # exists for referential integrity and audit convenience.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)

    revoked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # The access token's OWN expiry (session.created_at + ACCESS_TOKEN_EXPIRE_MINUTES),
    # not this row's -- once real, kept only so a cleanup task can purge
    # rows for tokens that would already fail on expiry anyway, without
    # this table growing forever. See api/tasks/token_blacklist_cleanup.py.
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
