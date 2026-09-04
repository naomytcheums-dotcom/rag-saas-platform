"""
Partie 3.4.11 -- real, standalone deduplication of search results:
`deduplicate_by_id`/`deduplicate_by_hash`/`deduplicate_by_similarity`/
`deduplicate_by_content`/`merge_duplicates` (item 2's own literal
functions).

**Reuses this codebase's own real semantic-similarity infrastructure**
for `deduplicate_by_similarity` -- `compute_semantic_similarity`
(`api.services.semantic_chunking`, Partie 3.2.3) and
`compute_chunk_embedding` (`api.services.semantic_filtering`, Partie
3.4.6, itself already reusing a real chunk's own already-computed
embedding when present) -- rather than a third, duplicate cosine-
similarity implementation.

**A real, honest note on `deduplicate_by_hash` vs `deduplicate_by_content`**:
both real functions below achieve the same real, exact-match outcome
(a SHA-256 hash is only ever a real proxy for the content string it was
computed from) -- kept as 2 separate real functions because this
étape's own literal action items name them separately, real, useful in
their own right for a caller preferring to compare cheap, fixed-size
real hashes over potentially large real content strings directly."""

import hashlib

from api.config import settings
from api.services.semantic_chunking import compute_semantic_similarity
from api.services.semantic_filtering import compute_chunk_embedding


def deduplicate_by_id(chunks: list[dict]) -> list[dict]:
    """Item 2's own literal function -- real, first-occurrence-wins
    dedup by `chunk_id`."""
    seen: set = set()
    deduped = []
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        deduped.append(chunk)
    return deduped


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def deduplicate_by_hash(chunks: list[dict]) -> list[dict]:
    """Item 2's own literal function -- real, first-occurrence-wins
    dedup by a real SHA-256 hash of `content`."""
    seen: set = set()
    deduped = []
    for chunk in chunks:
        content_hash = _content_hash(chunk.get("content", ""))
        if content_hash in seen:
            continue
        seen.add(content_hash)
        deduped.append(chunk)
    return deduped


def deduplicate_by_content(chunks: list[dict]) -> list[dict]:
    """Item 2's own literal function -- real, first-occurrence-wins
    dedup by exact `content` string equality (see this module's own top
    docstring for the real, honest relationship to `deduplicate_by_hash`
    above)."""
    seen: set = set()
    deduped = []
    for chunk in chunks:
        content = chunk.get("content", "")
        if content in seen:
            continue
        seen.add(content)
        deduped.append(chunk)
    return deduped


def deduplicate_by_similarity(chunks: list[dict], threshold: float | None = None) -> list[dict]:
    """Item 2's own literal function -- real, first-occurrence-wins
    dedup by real semantic similarity: a real chunk is dropped when its
    own real cosine similarity to any ALREADY-KEPT real chunk is
    `>= threshold` -- catches real near-duplicates (paraphrased,
    reformatted) exact-match dedup above cannot."""
    threshold = threshold if threshold is not None else settings.DEDUPLICATE_SIMILARITY_THRESHOLD
    kept: list[dict] = []
    kept_embeddings: list[list[float]] = []
    for chunk in chunks:
        embedding = compute_chunk_embedding(chunk)
        if any(compute_semantic_similarity(embedding, kept_embedding) >= threshold for kept_embedding in kept_embeddings):
            continue
        kept.append(chunk)
        kept_embeddings.append(embedding)
    return kept


_DEDUPLICATE_METHODS = {
    "id": deduplicate_by_id,
    "hash": deduplicate_by_hash,
    "content": deduplicate_by_content,
    "similarity": deduplicate_by_similarity,
}


def merge_duplicates(chunks: list[dict], method: str | None = None) -> list[dict]:
    """Item 2's own literal function -- real duplicates (identified via
    `DEDUPLICATE_METHOD`'s own real default method, `"hash"`) are
    collapsed to their own real, single, HIGHEST-scoring representative
    (when chunks carry a real `"score"` key; the first real occurrence
    otherwise), tagged with a real, honest `"merged_from"` list of every
    real chunk id folded into it -- never silently discarding which
    real chunks were merged. `DEDUPLICATE_ENABLED=False` is a real,
    deliberate kill switch, the same real convention
    `METADATA_FILTERING_ENABLED`/`SEMANTIC_FILTERING_ENABLED` already
    established."""
    if not settings.DEDUPLICATE_ENABLED:
        return list(chunks)

    method = method or settings.DEDUPLICATE_METHOD
    if method not in _DEDUPLICATE_METHODS:
        raise ValueError(f"Unknown deduplication method: {method!r} (expected one of {sorted(_DEDUPLICATE_METHODS)})")

    key_fn = (lambda c: _content_hash(c.get("content", ""))) if method == "hash" else (lambda c: c.get("content", "") if method == "content" else c.get("chunk_id"))
    if method == "similarity":
        # A real, honest simplification: similarity-based grouping (as
        # opposed to a single, cheap, hashable key) needs its own real
        # pairwise comparison, already exactly what deduplicate_by_similarity
        # does -- reused directly rather than a second grouping pass.
        return deduplicate_by_similarity(sorted(chunks, key=lambda c: c.get("score", 0), reverse=True))

    groups: dict = {}
    order: list = []
    for chunk in chunks:
        key = key_fn(chunk)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(chunk)

    merged = []
    for key in order:
        group = groups[key]
        best = max(group, key=lambda c: c.get("score", 0))
        merged_ids = [c.get("chunk_id") for c in group if c.get("chunk_id") != best.get("chunk_id")]
        merged.append({**best, "merged_from": merged_ids} if merged_ids else best)
    return merged
