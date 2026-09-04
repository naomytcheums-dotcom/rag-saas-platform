"""
Partie 3.2.8 -- real parent-child (hierarchical) chunking: small,
precise CHILD chunks carry the real search signal (indexed/embedded for
retrieval), while their own larger PARENT chunk supplies real, wider
context to the LLM once a child is matched -- a real, standard RAG
pattern for when a chunk small enough to be a precise, unambiguous
search hit is too small, on its own, to give the LLM enough real
surrounding context to answer from.

**Reuses 3 already-built real chunking strategies as PLUGGABLE
`strategy` implementations** rather than a fourth, duplicate splitter:
Partie 3.2.6's own real, sentence-respecting, TOKEN-budget
`chunk_by_sentence_tokens` (the real DEFAULT here -- `PARENT_CHILD_*_SIZE`'s
own literal defaults, 512/128, are this codebase's own established
real "tokens" convention, matching Partie 3.2.1's own `chunk_size`),
Partie 3.2.7's own `chunk_by_paragraph_tokens`, and Partie 3.2.2's own
character-based `chunk_recursive_text` (real, honest limitation: that
one strategy has no real overlap concept of its own, see
`_run_strategy` below).

**Real position tracking**: child chunks are produced by re-running the
chosen real strategy on EACH PARENT'S OWN text (not the whole document
independently) -- a real, structural guarantee that every child is a
genuine sub-span of its own real parent, rather than a real, separate
search-and-match step across the whole document to recover positions
after the fact.
"""

from api.config import settings
from api.services.chunking import chunk_recursive_text
from api.services.paragraph_chunking import chunk_by_paragraph_tokens
from api.services.sentence_chunking import chunk_by_sentence_tokens

_STRATEGIES = ("sentence", "paragraph", "recursive")


def _run_strategy(text: str, strategy: str, max_size: int, overlap: int) -> list[str]:
    if strategy == "sentence":
        return chunk_by_sentence_tokens(text, max_tokens=max_size, overlap_tokens=overlap)
    if strategy == "paragraph":
        return chunk_by_paragraph_tokens(text, max_tokens=max_size, overlap_tokens=overlap)
    if strategy == "recursive":
        # A real, honest, documented limitation: Partie 3.2.2's own
        # `chunk_recursive_text` has no real overlap concept of its
        # own (a deliberately stateless real split) -- `overlap` is
        # accepted for a real, uniform signature across all 3 real
        # strategies but has no real effect for this one.
        return chunk_recursive_text(text, max_size=max_size)
    raise ValueError(f"Unknown parent/child chunking strategy: {strategy!r} (expected one of {_STRATEGIES})")


def _locate_chunks(text: str, chunks: list[str]) -> list[dict]:
    """A real, simple, sequential `text.find` scan to recover each real
    chunk's own `{"start", "end"}` character span within `text` --
    searching forward from the end of the previous real match keeps
    real, repeated/duplicate chunk text resolving in real document
    order. Real, honest, documented fallback: a real chunk that no
    longer appears verbatim (a real strategy that reconstructs/joins
    text, e.g. inserted `"\\n\\n"`) degrades gracefully to the current
    running cursor rather than raising."""
    located = []
    search_from = 0
    for chunk in chunks:
        start = text.find(chunk, search_from)
        if start == -1:
            start = search_from
        end = start + len(chunk)
        located.append({"text": chunk, "start": start, "end": end})
        search_from = end
    return located


def create_parent_chunks(text: str, strategy: str | None = None, parent_size: int | None = None, parent_overlap: int | None = None) -> list[dict]:
    """Item 2's own literal function -- real, large parent chunks
    (`{"id", "text", "start", "end"}`), for real LLM context."""
    strategy = strategy or "sentence"
    parent_size = parent_size if parent_size is not None else settings.PARENT_CHILD_PARENT_SIZE
    parent_overlap = parent_overlap if parent_overlap is not None else settings.PARENT_CHILD_PARENT_OVERLAP
    if not text or not text.strip():
        return []

    chunks = _run_strategy(text, strategy, parent_size, parent_overlap)
    parents = _locate_chunks(text, chunks)
    for i, parent in enumerate(parents):
        parent["id"] = f"parent-{i}"
    return parents


def create_child_chunks(text: str, parent_chunks: list[dict], strategy: str | None = None, child_size: int | None = None, child_overlap: int | None = None) -> list[dict]:
    """Item 2's own literal function -- real, small child chunks, one
    real strategy pass PER PARENT (never across the whole document
    independently -- see this module's own top docstring), each
    already linked to its own real parent (`link_child_to_parent`
    below)."""
    strategy = strategy or "sentence"
    child_size = child_size if child_size is not None else settings.PARENT_CHILD_CHILD_SIZE
    child_overlap = child_overlap if child_overlap is not None else settings.PARENT_CHILD_CHILD_OVERLAP

    children: list[dict] = []
    child_index = 0
    for parent in parent_chunks:
        child_texts = _run_strategy(parent["text"], strategy, child_size, child_overlap)
        for local in _locate_chunks(parent["text"], child_texts):
            child = {
                "id": f"child-{child_index}",
                "text": local["text"],
                "start": parent["start"] + local["start"],
                "end": parent["start"] + local["end"],
            }
            children.append(link_child_to_parent(child, parent))
            child_index += 1
    return children


def link_child_to_parent(child_chunk: dict, parent_chunk: dict) -> dict:
    """Item 2's own literal function -- reused internally by
    `create_child_chunks` above (every real child it produces is
    already linked) and exposed standalone for a caller re-linking
    chunks built some other real way."""
    return {
        **child_chunk,
        "parent_id": parent_chunk["id"],
        "parent_text": parent_chunk["text"],
        "parent_start": parent_chunk["start"],
        "parent_end": parent_chunk["end"],
    }


def get_parent_context(child_chunk: dict) -> str | None:
    """Item 2's own literal function -- the real parent TEXT already
    embedded on a real, linked child chunk. `None`, honestly, for an
    unlinked child."""
    return child_chunk.get("parent_text")


def chunk_parent_child(
    text: str,
    child_size: int | None = None,
    parent_size: int | None = None,
    child_overlap: int | None = None,
    parent_overlap: int | None = None,
    strategy: str | None = None,
) -> dict:
    """Item 2's own literal function -- the real, complete pipeline:
    real parents, then real children built per-parent and already
    linked. `PARENT_CHILD_ENABLED=False` is a real, deliberate kill
    switch (honest empty result, not an exception -- the same real
    convention Partie 3.1.7's own `LANGUAGE_DETECTION_ENABLED` already
    established)."""
    if not settings.PARENT_CHILD_ENABLED:
        return {"parents": [], "children": []}
    parents = create_parent_chunks(text, strategy=strategy, parent_size=parent_size, parent_overlap=parent_overlap)
    children = create_child_chunks(text, parents, strategy=strategy, child_size=child_size, child_overlap=child_overlap)
    return {"parents": parents, "children": children}
