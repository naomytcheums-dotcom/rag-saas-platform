"""Request/response bodies for api/routers/email_domains.py (Partie
1.4.5). Deliberately has NO field for the DKIM private key anywhere --
see api/security/email_domains.py's own docstring on why it's encrypted
at rest; it must also never be returned by any API response, encrypted
or not."""

import datetime as dt
import uuid

from pydantic import BaseModel


class EmailDnsRecordEntry(BaseModel):
    type: str
    name: str
    value: str
    purpose: str


class EmailDnsResponse(BaseModel):
    # This app's own two records (ownership token + our own DKIM TXT) --
    # see api/security/email_domains.py's module docstring for why these
    # are real but NOT what Resend actually uses to sign mail.
    our_records: list[EmailDnsRecordEntry]
    # Resend's real Domain object id/status/records for this SAME
    # domain, fetched live -- None until ensure_email_domain_setup has
    # managed to register with Resend at least once.
    resend_domain_id: str | None
    resend_status: str | None
    resend_records: list[dict[str, object]] | None
    # Set only when Resend was unreachable/errored on THIS call -- the
    # request still succeeds (200) with our_records populated either way.
    resend_error: str | None


class EmailDomainStatusResponse(BaseModel):
    id: uuid.UUID
    domain: str
    status: str
    email_verified: bool
    email_verification_attempts: int
    email_verification_started_at: dt.datetime | None
    email_verified_at: dt.datetime | None
    timeout_at: dt.datetime | None
    dkim_configured: bool
