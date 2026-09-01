"""
1.1.7's true last resort -- for a user who has lost BOTH their
authenticator device AND all 10 recovery codes (api/models/recovery_code.py),
and so can satisfy neither /2fa/verify-login nor /2fa/verify-recovery-code.
See api/routers/two_factor.py's request/confirm_two_factor_lockout_recovery
for the mandatory delay this token's created_at is measured against, and
config.py's TWO_FA_LOCKOUT_RECOVERY_* settings for the actual durations.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class TwoFactorLockoutRecoveryToken(Base):
    __tablename__ = "two_factor_lockout_recovery_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # The delay before this token becomes usable is computed from this
    # column at confirm time (created_at + TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS),
    # rather than stored as its own field -- one source of truth for
    # "when was this requested" instead of two timestamps that could
    # theoretically disagree.
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
