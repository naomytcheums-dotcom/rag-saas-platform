"""
Audit finding 26 -- WebAuthn/FIDO2 credentials (hardware security keys
like a YubiKey, platform authenticators like Touch ID/Windows Hello),
used as a second factor alongside -- never instead of -- the existing
TOTP flow (api/models/user.py's totp_enabled). A user may register
several (WEBAUTHN_MAX_CREDENTIALS_PER_USER), the same way GitHub/Google
let an account hold more than one security key so losing one doesn't
lock anyone out.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # The authenticator-assigned credential ID -- opaque bytes, NOT a
    # secret (it's sent back and forth in plaintext on every
    # authentication ceremony; what makes WebAuthn secure is the private
    # key that never leaves the authenticator, not this identifier being
    # hidden). Unique globally, not just per-user: it's how
    # POST /auth/webauthn/authenticate/verify looks up WHICH user is
    # authenticating before it knows who's asking (the assertion response
    # carries the credential id, not a user id).
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, unique=True, index=True, nullable=False)
    # The credential's COSE public key -- used to verify every future
    # assertion's signature. Never a secret (it's a PUBLIC key), unlike
    # api/models/user.py's totp_secret.
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Replay-attack defense: every assertion response includes the
    # authenticator's own strictly-increasing use counter; if a fresh
    # counter isn't STRICTLY greater than this stored value, the
    # authenticator has likely been cloned (see api/security/webauthn.py's
    # verify_authentication -- rejects instead of just logging).
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Comma-separated transport hints the authenticator reported at
    # registration ("usb", "nfc", "ble", "internal") -- purely advisory,
    # lets the frontend hint the right UI ("insert your security key")
    # without guessing; never used for any security decision.
    transports: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # User-supplied label ("YubiKey 5C - work laptop") so someone with
    # several keys registered can tell them apart in GET /auth/webauthn/credentials
    # and know which one to remove.
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
