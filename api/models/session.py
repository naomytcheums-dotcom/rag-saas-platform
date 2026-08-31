"""
1.1.8 / 1.1.9 -- one row per issued refresh token. Only a SHA-256 hash of
the refresh token is ever stored (see api/security/hashing.py's
hash_token) -- a stolen DB dump must not itself be enough to impersonate a
session, the same reasoning as never storing a plaintext password.

Rotation (1.1.8): POST /auth/refresh revokes the row it consumed and
inserts a new one, rather than updating the token in place, so a reused
(stolen + already-rotated) refresh token is detectable -- it will fail the
"not revoked" check on its second use.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.utils import as_aware_utc


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6-safe length

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and as_aware_utc(self.expires_at) > dt.datetime.now(dt.timezone.utc)
