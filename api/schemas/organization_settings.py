"""Request/response bodies for api/routers/organization_settings.py
(Partie 1.3.9)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from api.config import settings
from api.security.organization_settings import is_valid_timezone
from api.services.chunk_config import CHUNKING_STRATEGIES


class OrganizationSettingsResponse(BaseModel):
    organization_id: uuid.UUID
    chunk_size: int
    chunk_overlap: int
    chunking_strategy: str
    # Phase 4, Étape 1 (correctif config parent_child) -- only ever read
    # when chunking_strategy="parent_child" (api/security/documents.py);
    # the other 7 strategies keep using chunk_size/chunk_overlap above,
    # completely unchanged.
    parent_chunk_size: int
    parent_chunk_overlap: int
    child_chunk_size: int
    child_chunk_overlap: int
    embedding_model: str
    llm_provider: str
    # Real `| None` -- honestly reflects DEFAULT_SETTINGS["llm_model"]'s
    # own real `None` (Partie 7.3's own bug fix, see
    # organization_settings.py's own docstring): `null` here means "no
    # real, explicit override -- this organization's own real calls
    # resolve to its provider's own live default model", never a
    # fabricated placeholder string.
    llm_model: str | None
    temperature: float
    top_p: float
    top_k: int
    reranker_model: str
    system_prompt: str
    retrieval_strategy: str
    max_tokens: int
    citation_required: bool
    citation_count: int
    language: str
    timezone: str
    score_threshold: float
    rrf_k: int
    # Phase 4, Étape 2 (Advanced Retrieval) -- see
    # api/security/organization_settings.py's own DEFAULT_SETTINGS
    # docstring for why every one of these 7 new fields defaults to
    # False/the pre-existing global default.
    query_rewriting_enabled: bool
    multi_query_enabled: bool
    multi_query_count: int
    hyde_enabled: bool
    mmr_enabled: bool
    mmr_lambda: float
    context_compression_enabled: bool


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
    # Phase 4, Étape 1 -- validated against the SAME real
    # `CHUNKING_STRATEGIES` tuple `chunk_content`'s own dispatch uses,
    # not a second, independently-typed literal that could drift.
    chunking_strategy: Literal[*CHUNKING_STRATEGIES] | None = None
    # Phase 4, Étape 1 (correctif config parent_child) -- same real
    # upper bound as chunk_size (a "tokens per chunk" ceiling is the
    # same real concept regardless of which strategy uses it, no second,
    # parallel ceiling constant).
    parent_chunk_size: int | None = Field(default=None, ge=1, le=settings.CHUNK_SIZE_MAX_TOKENS, description="Tokens per parent chunk (parent_child strategy only)")
    parent_chunk_overlap: int | None = Field(default=None, ge=0, description="Token overlap between consecutive parent chunks (parent_child strategy only)")
    child_chunk_size: int | None = Field(default=None, ge=1, le=settings.CHUNK_SIZE_MAX_TOKENS, description="Tokens per child chunk (parent_child strategy only)")
    child_chunk_overlap: int | None = Field(default=None, ge=0, description="Token overlap between consecutive child chunks (parent_child strategy only)")
    embedding_model: str | None = Field(default=None, min_length=1, max_length=200)
    # Widened for Partie 4.1.1-4.1.6's own real, now-supported providers
    # (was 3 -- anthropic/openai/gemini only). See
    # api/services/llm_providers.py's own top docstring for the real
    # dispatch behind each of these 6.
    llm_provider: Literal["anthropic", "openai", "gemini", "mistral", "ollama", "openai_compatible"] | None = None
    llm_model: str | None = Field(default=None, min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    # Partie 4.3.3 -- real, standard nucleus-sampling bounds.
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
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
    # Partie 4.3.5's own real, genuine gap fix: max_tokens previously
    # had no upper bound at all (`ge=1` only) -- real ceiling matching
    # that étape's own literal ask ("Max: 32768").
    max_tokens: int | None = Field(default=None, ge=1, le=settings.MAX_TOKENS_CEILING)
    citation_required: bool | None = None
    # Partie 6.1.1 -- real bound shared with api.services.citations'
    # own get_citation_count resolver (never a second, independently
    # hardcoded ceiling).
    citation_count: int | None = Field(default=None, ge=1, le=settings.CITATION_MAX_COUNT)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}(-[A-Z]{2})?$", description="e.g. 'en', 'fr', 'en-US'")
    timezone: str | None = Field(default=None, description="IANA timezone name, e.g. 'UTC', 'Europe/Paris'")
    # Partie 3.3.7 -- real, fixed 0.0-1.0 bounds (a real, normalized
    # similarity score can never be outside this range by construction,
    # see api/services/retrieval_pipeline.py's own real
    # min-max-normalization step), not an operationally-tunable ceiling
    # the way CHUNK_SIZE_MAX_TOKENS/TOP_K_MAX are.
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    # Partie 3.4.7 -- real bounds matching that étape's own literal ask
    # ("Min: 1, Max: 1000").
    rrf_k: int | None = Field(default=None, ge=1, le=1000)
    # Phase 4, Étape 2 (Advanced Retrieval) -- real bounds matching each
    # new resolver's own real validation in
    # api/services/retrieval_config.py (never a second, independently
    # hardcoded ceiling).
    query_rewriting_enabled: bool | None = None
    multi_query_enabled: bool | None = None
    multi_query_count: int | None = Field(default=None, ge=1, le=10, description="Number of query variants generated, including the original query")
    hyde_enabled: bool | None = None
    mmr_enabled: bool | None = None
    mmr_lambda: float | None = Field(default=None, ge=0.0, le=1.0, description="MMR relevance/diversity trade-off: 0 = max diversity, 1 = max relevance")
    context_compression_enabled: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str | None) -> str | None:
        if value is not None and not is_valid_timezone(value):
            raise ValueError(f"Unknown IANA timezone: {value!r}")
        return value
