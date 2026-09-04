"""Request/response bodies for api/routers/search.py (Partie 3.3.4-3.3.7)."""

from typing import Literal

from pydantic import BaseModel, Field

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
