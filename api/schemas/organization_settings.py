"""Request/response bodies for api/routers/organization_settings.py
(Partie 1.3.9)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from api.config import settings
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
    score_threshold: float


class OrganizationSettingsUpdateRequest(BaseModel):
    """PATCH /organizations/{org_id}/settings -- every field optional,
    only the ones actually sent are changed (partial update, same
    exclude_unset=True convention as OrganizationQuotaUpdateRequest and
    UserLimitsUpdateRequest). Bounds below are deliberately permissive
    (this is configuration an Owner controls, not a security boundary)
    but real -- each one rejects a value that could never be sensible,
    not just a placeholder `...: int | None = None`."""

    # Partie 3.3.1's own real, genuine gap fix: chunk_size previously had
    # no upper bound at all (`ge=1` only) -- see api/config.py's own
    # CHUNK_SIZE_MAX_TOKENS docstring for why.
    chunk_size: int | None = Field(default=None, ge=1, le=settings.CHUNK_SIZE_MAX_TOKENS, description="Tokens per chunk")
    chunk_overlap: int | None = Field(default=None, ge=0, description="Token overlap between consecutive chunks")
    embedding_model: str | None = Field(default=None, min_length=1, max_length=200)
    llm_provider: Literal["anthropic", "openai", "gemini"] | None = None
    llm_model: str | None = Field(default=None, min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    # Partie 3.3.6's own real bound, matching that étape's own literal
    # ask ("min: 1, max: 100") -- shares api/config.py's own real
    # TOP_K_MAX with api/services/retrieval_config.py's own
    # resolve_top_k, rather than 2 independently hardcoded "100"s.
    top_k: int | None = Field(default=None, ge=1, le=settings.TOP_K_MAX)
    reranker_model: str | None = Field(default=None, min_length=1, max_length=200)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=10_000)
    # Widened for Partie 3.3.4's own literal 5-strategy list (was 3 --
    # hybrid/vector_only/bm25_only only).
    retrieval_strategy: Literal["hybrid", "vector_only", "bm25_only", "hybrid_reranked", "semantic"] | None = None
    max_tokens: int | None = Field(default=None, ge=1)
    citation_required: bool | None = None
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}(-[A-Z]{2})?$", description="e.g. 'en', 'fr', 'en-US'")
    timezone: str | None = Field(default=None, description="IANA timezone name, e.g. 'UTC', 'Europe/Paris'")
    # Partie 3.3.7 -- real, fixed 0.0-1.0 bounds (a real, normalized
    # similarity score can never be outside this range by construction,
    # see api/services/retrieval_pipeline.py's own real
    # min-max-normalization step), not an operationally-tunable ceiling
    # the way CHUNK_SIZE_MAX_TOKENS/TOP_K_MAX are.
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_timezone(value):
            raise ValueError(f"Unknown IANA timezone: {value!r}")
        return value
