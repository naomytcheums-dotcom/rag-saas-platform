"""
Audit finding 15 -- keeps a user's most recent password hashes so a new
password can be checked against them (api/security/password_history.py),
independent of `User.hashed_password` itself (the CURRENT password, never
stored here twice -- see that module's docstring for how the two are
combined at check time).

Only the most recent PASSWORD_HISTORY_SIZE rows per user are ever kept
(pruned by api/security/password_history.py's record_password_change() on
every write) -- this table is a short reuse-check window, not a permanent
password audit log.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class PasswordHistory(Base):
    __tablename__ = "password_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Same bcrypt hash format as User.hashed_password -- a stored former
    # password is exactly as sensitive as the current one, salted and
    # slow to brute-force the same way.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
