"""
1.1.12's flip side -- lets a user who withdrew consent (POST /account/consent/withdraw)
come back, without that being a silent one-way door. Deliberately a
separate token type from AccountRestoreToken even though the shape is
identical: they gate two different account states (consent_withdrawn_at
vs deleted_at) with two different consequences on confirm, and mixing
them into one shared table would let a token issued for one purpose be
replayed against the other code path by accident.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ConsentReactivationToken(Base):
    __tablename__ = "consent_reactivation_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Null until used to reactivate the account -- see
    # api/routers/account.py's confirm_consent_reactivation().
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
