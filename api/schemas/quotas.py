"""Request/response bodies for api/routers/quotas.py (Partie 1.3.6)."""

import uuid

from pydantic import BaseModel, Field


class QuotaDimensionEntry(BaseModel):
    limit: int
    # None means "not measured yet" (no real table/endpoint exists for
    # this resource type) -- distinct from 0, which would claim "nothing
    # used." See api/security/quotas.py's module docstring.
    used: int | None


class OrganizationQuotaResponse(BaseModel):
    organization_id: uuid.UUID
    users: QuotaDimensionEntry
    workspaces: QuotaDimensionEntry
    teams: QuotaDimensionEntry
    documents: QuotaDimensionEntry
    storage_mb: QuotaDimensionEntry
    requests_per_month: QuotaDimensionEntry
    requests_per_day: QuotaDimensionEntry
    api_calls: QuotaDimensionEntry
    agents: QuotaDimensionEntry
    kb_size_mb: QuotaDimensionEntry


class OrganizationQuotaUpdateRequest(BaseModel):
    """Body of PATCH /organizations/{org_id}/quotas -- every field
    optional, only the ones actually sent are changed (partial update).
    `ge=0`: a limit of 0 is a valid, deliberate way to hard-block a
    resource type entirely (e.g. suspending an organization), not
    rejected as invalid."""

    max_users: int | None = Field(default=None, ge=0)
    max_workspaces: int | None = Field(default=None, ge=0)
    max_teams: int | None = Field(default=None, ge=0)
    max_documents: int | None = Field(default=None, ge=0)
    max_storage_mb: int | None = Field(default=None, ge=0)
    max_requests_per_month: int | None = Field(default=None, ge=0)
    max_requests_per_day: int | None = Field(default=None, ge=0)
    max_api_calls: int | None = Field(default=None, ge=0)
    max_agents: int | None = Field(default=None, ge=0)
    max_kb_size_mb: int | None = Field(default=None, ge=0)
