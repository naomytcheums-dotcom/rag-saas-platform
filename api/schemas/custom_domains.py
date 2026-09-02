"""Request/response bodies for api/routers/custom_domains.py
(Partie 1.4.1)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class CustomDomainCreateRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=255, description="e.g. 'app.ma-boite.com'")


class DnsRecordEntry(BaseModel):
    type: str
    name: str
    value: str


class CustomDomainResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    domain: str
    status: str
    verification_token: str
    # Computed fresh from `domain`/`verification_token` on every
    # response (api/security/custom_domains.py's dns_records_for) --
    # never stored, so a CUSTOM_DOMAIN_CNAME_TARGET change instantly
    # applies to every domain's instructions, not just newly-created ones.
    dns_records: list[DnsRecordEntry]
    created_at: dt.datetime
    updated_at: dt.datetime


class CustomDomainListResponse(BaseModel):
    items: list[CustomDomainResponse]
