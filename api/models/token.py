"""
1.1.3 (password reset) and 1.1.4 (email verification OTP). Same
hash-not-plaintext reasoning as Session's refresh_token_hash.

EmailVerificationToken.attempts guards against a script brute-forcing a
6-digit code (1,000,000 possibilities -- trivial without a limit); it's
capped and checked in the verify_email router, not here, since "what to do
once exceeded" is a request-handling decision, not a storage concern.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Null until the link is actually used to reset the password; once
    # set, the token is dead even if it hasn't expired yet -- see
    # api/routers/password.py's reset_password().
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
