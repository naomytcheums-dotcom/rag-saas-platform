"""Request/response bodies for api/routers/search.py (Partie 3.3.4-3.3.7)."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Kept as a real, literal duplicate of
# `api.services.retrieval_config.RETRIEVAL_STRATEGIES` -- a Pydantic
# `Literal` needs its own real, static tuple (it cannot be built from a
# runtime import the way `api/schemas/organization_settings.py`'s own
# `retrieval_strategy` field can't either); a change to one real,
# small, 5-item set is easy to keep in sync by hand.
_STRATEGY_LITERAL = Literal["hybrid", "vector_only", "bm25_only", "hybrid_reranked", "semantic"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=100)
    strategy: _STRATEGY_LITERAL | None = None
    reranker: str | None = Field(default=None, min_length=1, max_length=200)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    # Phase 4, Étape 3 (Metadata Filtering) -- real, optional, additive
    # request-time filter (this étape's own literal API shape:
    # `{"department": "finance", "year": 2026}`, or
    # `{"year": {"gt": 2020}}`). Real, deliberate `None` default --
    # rétrocompatibilité's own explicit ask (requirement 20): an
    # existing `{"query": "..."}` request keeps working byte-identically.
    # Validated here (real, early rejection -- a malformed filter never
    # even reaches `api.services.retrieval_pipeline.search`) by the SAME
    # real function that function's own runtime, fail-fast check also
    # calls (`api.services.metadata_filtering.normalize_metadata_filters`)
    # -- never a second, independently-drifting validation rule.
    filters: dict | None = None

    @field_validator("filters")
    @classmethod
    def _validate_filters(cls, value: dict | None) -> dict | None:
        if value is None:
            return None
        from api.services.metadata_filtering import normalize_metadata_filters

        normalize_metadata_filters(value)
        return value


class SearchResultContext(BaseModel):
    document_name: str
    file_type: str
    metadata: dict | None = None


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    file_type: str
    content: str
    score: float
    # Partie 3.3.7 -- the same real score above, min-max normalized
    # against the rest of this real result set (see
    # api/services/retrieval_pipeline.py's own `_normalize_scores`) --
    # this is the real value `score_threshold` is actually applied
    # against, exposed here so a caller can see why a result survived.
    normalized_score: float | None = None
    metadata_json: dict | None = None
    context: SearchResultContext | None = None


class SearchResponse(BaseModel):
    query: str
    strategy: str
    results: list[SearchResult]
