"""Request/response bodies for api/routers/organization_settings.py
(Partie 1.3.9)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from api.security.organization_settings import is_valid_timezone


class OrganizationSettingsResponse(BaseModel):
    organization_id: uuid.UUID
    chunk_size: int
    chunk_overlap: int
    embedding_model: str
    llm_provider: str
    llm_model: str
    temperature: float
    top_k: int
    reranker_model: str
    system_prompt: str
    retrieval_strategy: str
    max_tokens: int
    citation_required: bool
    language: str
    timezone: str


class OrganizationSettingsUpdateRequest(BaseModel):
    """PATCH /organizations/{org_id}/settings -- every field optional,
    only the ones actually sent are changed (partial update, same
    exclude_unset=True convention as OrganizationQuotaUpdateRequest and
    UserLimitsUpdateRequest). Bounds below are deliberately permissive
    (this is configuration an Owner controls, not a security boundary)
    but real -- each one rejects a value that could never be sensible,
    not just a placeholder `...: int | None = None`."""

    chunk_size: int | None = Field(default=None, ge=1, description="Tokens per chunk")
    chunk_overlap: int | None = Field(default=None, ge=0, description="Token overlap between consecutive chunks")
    embedding_model: str | None = Field(default=None, min_length=1, max_length=200)
    llm_provider: Literal["anthropic", "openai", "gemini"] | None = None
    llm_model: str | None = Field(default=None, min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_k: int | None = Field(default=None, ge=1)
    reranker_model: str | None = Field(default=None, min_length=1, max_length=200)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=10_000)
    retrieval_strategy: Literal["hybrid", "vector_only", "bm25_only"] | None = None
    max_tokens: int | None = Field(default=None, ge=1)
    citation_required: bool | None = None
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}(-[A-Z]{2})?$", description="e.g. 'en', 'fr', 'en-US'")
    timezone: str | None = Field(default=None, description="IANA timezone name, e.g. 'UTC', 'Europe/Paris'")

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_timezone(value):
            raise ValueError(f"Unknown IANA timezone: {value!r}")
        return value
