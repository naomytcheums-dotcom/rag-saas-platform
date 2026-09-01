"""
1.1.7 2FA recovery codes -- see api/security/recovery_codes.py for why
these exist and how they're generated. Each row is one single-use code;
a fresh batch of RECOVERY_CODE_COUNT rows is created whenever 2FA is
enabled or the set is regenerated, and every row from the previous batch
is deleted at that point (see api/routers/two_factor.py) so an old,
possibly-leaked code can never work after a regeneration or a disable.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class TwoFactorRecoveryCode(Base):
    __tablename__ = "two_factor_recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # SHA-256 hash of the normalized code -- same reasoning as
    # Session.refresh_token_hash, the raw code is never stored.
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Null until this code is used to complete a login; once set, this
    # code is dead even though its row is kept as an audit trail of when
    # a recovery code was actually consumed. A failed guess just matches
    # no row and leaves everything as-is.
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
