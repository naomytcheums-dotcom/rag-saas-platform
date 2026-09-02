"""
Audit finding 28 -- DB-backed signing keys behind automatic JWT rotation.
Complements, rather than replaces, JWT_SECRET_KEY / JWT_PREVIOUS_SECRET_KEYS
(api/config.py): those remain the fallback signing/verification keys
until the first row here exists, and keep working unchanged for a manual
rotation or a leak response even after automatic rotation is enabled
(api/security/jwt.py tries both). See api/tasks/jwt_key_rotation.py for
how a row here gets created/retired, and that same module's docstring
for exactly how a running API process picks up a change without a
restart.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class JWTSigningKey(Base):
    __tablename__ = "jwt_signing_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Fernet-encrypted (api/security/secret_encryption.py) -- this is as
    # sensitive as JWT_SECRET_KEY itself, and unlike that env var, a
    # database row is realistically exposed by a broader class of
    # incidents (a backup, a read replica, a SQL-injection elsewhere) --
    # encryption-at-rest here is a real, low-cost hardening the env-var
    # form of this same secret doesn't get for free.
    secret: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # NULL means still active. Set the moment a rotation replaces this
    # key with a new active one -- a retired key remains valid for
    # VERIFYING already-issued tokens until JWT_KEY_RETENTION_DAYS after
    # this timestamp (api/security/jwt.py's refresh_jwt_key_cache), never
    # for signing a new one.
    retired_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
