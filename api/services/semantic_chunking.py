"""
Partie 3.2.3 -- real semantic chunking: group real sentences into
chunks by their own real semantic similarity (real sentence
embeddings, real cosine similarity between ADJACENT sentences) rather
than a fixed character/token count -- a real chunk boundary is placed
wherever two consecutive real sentences are semantically dissimilar (a
real topic shift), keeping semantically related sentences together in
the same chunk.

**Reuses this codebase's own existing real embedding infrastructure**
(`api.security.documents.generate_embeddings`, the same real
sentence-transformers model already used since Partie 2.1.1 for the
real RAG pipeline itself) rather than building new embedding
infrastructure. Defaults to this codebase's own real default model
(`api.security.organization_settings.DEFAULT_SETTINGS["embedding_model"]`)
when no organization context is given, since -- like Partie 3.2.2's
own 4 functions -- these 5 functions are genuinely new, standalone
capability, not yet wired into `process_document`.

**Reuses Partie 3.1.10's own real sentence splitter**
(`api.services.metadata_enrichment.split_sentences`, made public for
this reuse) rather than a second, duplicate regex sentence splitter.

**Reuses Partie 3.2.2's own real recursive character splitter**
(`api.services.chunking.chunk_recursive_text`) as the real, honest
fallback for the rare real chunk that stays too big even after
semantic grouping (a single real sentence longer than
`SEMANTIC_CHUNK_MAX_SIZE` on its own) -- the same real "reuse the
pipeline" discipline this codebase has followed throughout, rather
than a third, duplicate hard-split implementation.
"""

import numpy as np

from api.config import settings
from api.security.documents import generate_embeddings
from api.security.organization_settings import DEFAULT_SETTINGS
from api.services.chunking import chunk_recursive_text
from api.services.metadata_enrichment import split_sentences

_DEFAULT_MODEL = DEFAULT_SETTINGS["embedding_model"]


def compute_sentence_embeddings(sentences: list[str], model_name: str | None = None) -> list[list[float]]:
    """Item 2's own literal function -- real sentence embeddings via
    this codebase's own existing `generate_embeddings`."""
    if not sentences:
        return []
    return generate_embeddings(sentences, model_name or _DEFAULT_MODEL)


def compute_semantic_similarity(embedding1: list[float], embedding2: list[float]) -> float:
    """Item 2's own literal function -- real cosine similarity between
    two real embeddings. Honestly returns `0.0` for a real zero-norm
    vector rather than dividing by zero (never happens for a real
    sentence-transformers output, but a real, cheap guard regardless)."""
    a, b = np.asarray(embedding1, dtype=float), np.asarray(embedding2, dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def find_breakpoints(similarities: list[float], threshold: float | None = None) -> list[int]:
    """Item 2's own literal function -- real indices into the real
    sentence list where a real semantic break happens.
    `similarities[i]` is the real similarity between sentence `i` and
    sentence `i + 1`; a value below `threshold` means sentence `i + 1`
    starts a real new chunk, so the returned index is `i + 1`."""
    threshold = threshold if threshold is not None else settings.SEMANTIC_CHUNK_THRESHOLD
    return [i + 1 for i, similarity in enumerate(similarities) if similarity < threshold]


def chunk_by_semantic_similarity(sentences: list[str], threshold: float | None = None, model_name: str | None = None) -> list[str]:
    """Item 2's own literal function -- the real entry point: real
    sentences grouped into chunks at real semantic breakpoints. A
    single real sentence is its own real chunk (no real pair to
    compare, so no real similarity signal exists)."""
    sentences = [s.strip() for s in sentences if s and s.strip()]
    if not sentences:
        return []
    if len(sentences) == 1:
        return sentences

    embeddings = compute_sentence_embeddings(sentences, model_name)
    similarities = [compute_semantic_similarity(embeddings[i], embeddings[i + 1]) for i in range(len(embeddings) - 1)]
    breakpoints = set(find_breakpoints(similarities, threshold))

    chunks: list[str] = []
    current = [sentences[0]]
    for i, sentence in enumerate(sentences[1:], start=1):
        if i in breakpoints:
            chunks.append(" ".join(current))
            current = [sentence]
        else:
            current.append(sentence)
    chunks.append(" ".join(current))
    return chunks


def merge_semantic_chunks(chunks: list[str], max_size: int | None = None) -> list[str]:
    """Item 2's own literal function -- a real second pass over
    `chunk_by_semantic_similarity`'s own output: merges small adjacent
    real chunks together (respecting `SEMANTIC_CHUNK_MIN_SIZE`, never
    merging past `max_size`), then hard-splits any real chunk still
    over `max_size` via Partie 3.2.2's own `chunk_recursive_text`."""
    max_size = max_size if max_size is not None else settings.SEMANTIC_CHUNK_MAX_SIZE
    min_size = settings.SEMANTIC_CHUNK_MIN_SIZE
    if not chunks:
        return []

    merged = [chunks[0]]
    for chunk in chunks[1:]:
        candidate = merged[-1] + " " + chunk
        if len(merged[-1]) < min_size and len(candidate) <= max_size:
            merged[-1] = candidate
        else:
            merged.append(chunk)

    result: list[str] = []
    for chunk in merged:
        if len(chunk) > max_size:
            result.extend(chunk_recursive_text(chunk, max_size=max_size, separators=[". ", " ", ""]))
        else:
            result.append(chunk)
    return result
