"""
Partie 1.4.3 -- persists the ONE ACME account this deployment registers
with Let's Encrypt (or whichever ACME_DIRECTORY_URL is configured),
keyed by directory so staging and production each get their own
account if both are ever used. NOT named in this step's literal spec
(which only asks for an `SSLCertificate` table) -- added because ACME
account registration is genuinely per-deployment, not per-domain: RFC
8555 accounts are the identity that requests/owns certificates, and
that identity's private key must survive process restarts to keep
using the SAME account (re-registering a fresh key on every request
would create a new Let's Encrypt account each time, which works but is
wasteful and not how any real ACME client behaves).

`account_key_pem_encrypted` -- Fernet-encrypted via
api/security/secret_encryption.py, same module already protecting
JWTSigningKey/EnterpriseSSOConnection secrets (audit Categorie 4, items
27/28). This key can request/revoke every certificate this account has
ever issued -- it is exactly as sensitive as those two.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AcmeAccount(Base):
    __tablename__ = "acme_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    directory_url: Mapped[str] = mapped_column(String(500), nullable=False)
    account_key_pem_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # The ACME server's own URL identifying this account (RFC 8555's
    # "kid") -- required on every subsequent signed request.
    account_url: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("directory_url", name="uq_acme_accounts_directory_url"),
    )
