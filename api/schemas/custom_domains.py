"""Request/response bodies for api/routers/custom_domains.py
(Partie 1.4.1/1.4.2)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class CustomDomainCreateRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=255, description="e.g. 'app.ma-boite.com'")


class DnsRecordEntry(BaseModel):
    type: str
    name: str
    value: str
    # Partie 1.4.2 -- {"fr": "...", "en": "..."}, always both present.
    instructions: dict[str, str]


class CustomDomainResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    domain: str
    status: str
    verification_token: str
    # Partie 1.4.4 -- how many automatic polling attempts this domain
    # has had, and when the last one ran (None if it's never been
    # polled automatically yet -- a brand new domain, or one only ever
    # checked manually).
    verification_attempts: int
    last_verification_attempt_at: dt.datetime | None
    # Computed fresh from `domain`/`verification_token` on every
    # response (api/security/custom_domains.py's dns_records_for) --
    # never stored, so a CUSTOM_DOMAIN_CNAME_TARGET change instantly
    # applies to every domain's instructions, not just newly-created ones.
    dns_records: list[DnsRecordEntry]
    # Partie 1.4.2 -- ordered, non-technical walkthrough, both languages
    # (api/security/custom_domains.py's setup_steps -- a fixed constant,
    # not domain-specific).
    setup_steps: list[dict[str, str]]
    created_at: dt.datetime
    updated_at: dt.datetime


class CustomDomainListResponse(BaseModel):
    items: list[CustomDomainResponse]


class CustomDomainStatusResponse(BaseModel):
    """Partie 1.4.4's `GET .../status` -- a focused view of
    verification PROGRESS, distinct from CustomDomainResponse's fuller
    (DNS-instructions-included) shape: what a dashboard polling for
    "is it done yet" actually needs."""

    id: uuid.UUID
    domain: str
    status: str
    verification_attempts: int
    max_attempts: int
    last_verification_attempt_at: dt.datetime | None
    created_at: dt.datetime
    # created_at + DOMAIN_VERIFICATION_TIMEOUT_MINUTES, computed on the
    # fly (never stored) -- when this domain will be marked `failed` on
    # elapsed time alone, even if verification_attempts hasn't yet
    # reached max_attempts.
    timeout_at: dt.datetime
