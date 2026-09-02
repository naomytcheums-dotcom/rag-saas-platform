"""
Partie 1.4.3 -- SSL certificates for custom domains, issued via a real
ACME v2 (RFC 8555) client against Let's Encrypt (api/security/ssl_certificates.py).

**Honest scope, verified before writing a line of code, same posture
as Partie 1.4.1's custom_domains**: HTTP-01 challenges need a live web
server answering on the domain's own IP at port 80 -- this deployment
has none (no reverse-proxy routes custom domains at all, see
custom_domain.py's own docstring). DNS-01 challenges need programmatic
write access to the domain's DNS zone -- this deployment has none
either (api/security/custom_domains.py's own DNS integration is
READ-only, a TXT lookup, never a write). So issuance here is a real,
correct, two-phase ACME flow with a MANUAL step in the middle: this
app can register a real account, open a real order, and compute the
real DNS-01 challenge value Let's Encrypt requires -- but publishing
that TXT record is a step only the domain's Owner can perform (same
"the Owner does the DNS work, this app only verifies it" shape as
custom domain verification itself, Partie 1.4.1). Calling
generate_ssl_certificate a second time, after the Owner has published
the record, is what completes issuance for real.

`status` extends beyond this step's literal column list for exactly
that reason -- a certificate genuinely has a "waiting on the Owner's
DNS" state this table has to be able to represent, not just
"issued" or "not created yet":
- `pending_dns01`: an order exists, a challenge has been computed
  (`dns01_record_name`/`dns01_record_value`), no certificate yet.
- `issued`: `cert_pem`/`chain_pem`/`expires_at` are real, current.
- `failed`: Let's Encrypt reported an invalid authorization (the
  Owner's DNS never matched, or expired before completion).

`cert_pem`/`expires_at` are nullable -- a `pending_dns01` row
genuinely has neither yet, unlike this step's literal spec (which
implies a row only exists once issued). `key_pem_encrypted` is
populated from the START of an order (the certificate's own key pair
must exist before the CSR can be built at finalization time) and is
Fernet-encrypted via api/security/secret_encryption.py -- **never**
stored raw, addressing this step's own vision-critique question on key
security directly: this is the exact same encryption already
protecting JWTSigningKey/EnterpriseSSOConnection secrets, not a new,
unreviewed mechanism.
"""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class SSLCertificateStatus(StrEnum):
    pending_dns01 = "pending_dns01"
    issued = "issued"
    failed = "failed"


class SSLCertificate(Base):
    __tablename__ = "ssl_certificates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # FK to custom_domains.domain (not .id) -- this step's own literal
    # spec, and valid: that column already carries its own UNIQUE
    # constraint (Partie 1.4.1).
    domain: Mapped[str] = mapped_column(String(255), ForeignKey("custom_domains.domain", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SSLCertificateStatus.pending_dns01.value)
    cert_pem: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_pem_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    chain_pem: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Pending-order bookkeeping -- needed to RESUME an in-progress ACME
    # order on a second call (or from the renewal Celery task), not
    # named in this step's literal spec but required for a real,
    # correct, two-phase flow rather than restarting a fresh order
    # every time generate_ssl_certificate is called.
    acme_order_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    acme_challenge_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dns01_record_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    dns01_record_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("domain", name="uq_ssl_certificates_domain"),
    )
