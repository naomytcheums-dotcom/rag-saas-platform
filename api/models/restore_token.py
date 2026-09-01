"""
1.1.10's flip side -- lets a user who soft-deleted their own account
(DELETE /account/me) undo it before the grace period's automatic purge
(api/tasks/account_purge.py) runs and erases the row for good. Same shape
and hash-not-plaintext reasoning as PasswordResetToken (api/models/token.py);
kept in its own module because it belongs to a different feature, not
because the pattern differs.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AccountRestoreToken(Base):
    __tablename__ = "account_restore_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Null until the link is actually used to restore the account; once
    # set, the link is dead even if it hasn't expired yet -- see
    # api/routers/account.py's confirm_account_restore().
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
