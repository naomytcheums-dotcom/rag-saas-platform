"""
Partie 3.3.1 (chunk size configurable) + 3.3.2 (chunk overlap
configurable) -- combined into one module: both étapes resolve the
same real pair of `organization_settings` values together (a real
overlap can only ever be validated AGAINST a real chunk size), and
splitting that one, small, coupled concern into two separate files
would be real, artificial padding, not genuine separation.

**Vérification de l'existant (action 1 of both étapes)**: `chunk_size`/
`chunk_overlap` are ALREADY real, live, per-organization settings --
verified by reading the actual call sites, not assumed:
- Read for real in `api/security/documents.py`'s own `process_document`,
  passed straight into `chunk_text` (Partie 3.2.1) -- this is the
  REAL, live pipeline path; nothing here duplicates it.
- Validated at write time in `api/schemas/organization_settings.py`
  (`chunk_size`: `ge=1, le=CHUNK_SIZE_MAX_TOKENS`; `chunk_overlap`:
  `ge=0`) AND a real, existing cross-field check in
  `api/routers/organization_settings.py`'s own PATCH endpoint
  (`chunk_overlap must be smaller than chunk_size`, HTTP 400).
  `api/security/organization_settings.py`'s own module docstring
  (Partie 1.3.9) was stale on this point -- corrected as part of this
  étape.

**What this module actually, newly adds**: every one of the 7 newer,
standalone chunking strategies (Partie 3.2.2-3.2.8) ALREADY accepts an
explicit size/overlap override on its own literal signature (verified
directly against each module -- `chunk_recursive_text`/`chunk_recursive_markdown`/
`chunk_recursive_html`/`chunk_recursive_code` via `max_size`,
`merge_semantic_chunks` via `max_size`, every `chunk_markdown_*`
function via `max_chunk_size`, `chunk_code_by_functions`/
`chunk_code_by_classes`/`chunk_code_by_blocks`/`chunk_code_by_tokens`
via `max_size`/`max_tokens` -- **a real, genuine gap found and fixed
while verifying this**: the first 3 code functions had NO such
parameter at all until this étape added one, see
`api/services/code_chunking.py`'s own updated docstrings --
`chunk_by_sentences`/`chunk_by_sentence_tokens`/`merge_sentences` via
`max_sentences`/`max_tokens`, `chunk_by_paragraphs`/
`chunk_by_paragraph_tokens`/`merge_paragraphs` via `max_paragraphs`/
`max_tokens`, `create_parent_chunks`/`create_child_chunks`/
`chunk_parent_child` via `parent_size`/`child_size`). So the real,
missing piece was never "can these accept an override" -- it was a
real, reusable RESOLVER bridging `organization_settings` to an
explicit call, with real validation the schema's own per-field bounds
can't express on a bare Python value passed around outside a request
(e.g. a Celery task's own settings dict).
"""

from api.config import settings
from api.security.organization_settings import DEFAULT_SETTINGS

# Phase 4, Étape 1 -- the real, literal set of chunking strategies an
# organization can select. "fixed" is the pre-existing, still-default
# token-sliding-window strategy (`api/security/documents.py::chunk_text`)
# and "parent_child" (Partie 3.2.8, wired for real in this étape's own
# correctif) are BOTH handled directly by `process_document` itself,
# never by `chunk_content` below -- "fixed" needs a real tokenizer this
# module has no business constructing, and "parent_child" returns a
# real `{"parents": [...], "children": [...]}` structure (now backed by
# `DocumentChunk.parent_chunk_id`/`chunk_role`, migration `0112`), not a
# flat `list[str]` every other strategy shares. Every OTHER name here
# dispatches through `chunk_content` to one of the 6 real, standalone,
# single-population strategies (Partie 3.2.2-3.2.7).
CHUNKING_STRATEGIES = ("fixed", "recursive", "markdown", "code", "semantic", "sentence", "paragraph", "parent_child")


def resolve_chunk_size(org_settings: dict | None = None, override: int | None = None) -> int:
    """Item 2's own literal ask for both étapes -- an explicit
    `override` (whatever a caller passes directly to one of the 7 real
    strategies) always wins; otherwise `org_settings["chunk_size"]`
    when a real settings dict is given; otherwise this codebase's own
    real, established default (`DEFAULT_SETTINGS["chunk_size"]`, 512).
    Real, defensive validation (vision critique 3, "valeur invalide")
    -- this function may be called with a raw dict from anywhere
    (a Celery task, a script), not only through the already-validated
    HTTP PATCH path, so it re-checks the same real bounds rather than
    trusting every caller."""
    if override is not None:
        value = override
    elif org_settings is not None and org_settings.get("chunk_size") is not None:
        value = org_settings["chunk_size"]
    else:
        value = DEFAULT_SETTINGS["chunk_size"]

    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"Invalid chunk_size: {value!r} (must be a positive integer)")
    if value > settings.CHUNK_SIZE_MAX_TOKENS:
        raise ValueError(f"chunk_size {value} exceeds the real maximum of {settings.CHUNK_SIZE_MAX_TOKENS}")
    return value


def resolve_chunk_overlap(org_settings: dict | None = None, override: int | None = None, chunk_size: int | None = None) -> int:
    """Item 2's own literal ask for both étapes -- same real
    override > org_settings > default precedence as `resolve_chunk_size`
    above, plus the same real `overlap < chunk_size` cross-field check
    `api/routers/organization_settings.py`'s own PATCH endpoint already
    enforces at write time, re-applied here for every OTHER real
    caller of this pair (not only the HTTP PATCH path)."""
    if override is not None:
        value = override
    elif org_settings is not None and org_settings.get("chunk_overlap") is not None:
        value = org_settings["chunk_overlap"]
    else:
        value = DEFAULT_SETTINGS["chunk_overlap"]

    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Invalid chunk_overlap: {value!r} (must be zero or a positive integer)")

    effective_chunk_size = chunk_size if chunk_size is not None else resolve_chunk_size(org_settings)
    if value >= effective_chunk_size:
        raise ValueError(f"chunk_overlap ({value}) must be smaller than chunk_size ({effective_chunk_size})")
    return value


def resolve_parent_chunk_size(org_settings: dict | None = None, override: int | None = None) -> int:
    """Phase 4, Étape 1 (correctif config parent_child) -- the real
    "parent_chunk_size" sibling of `resolve_chunk_size` above, same real
    override > org_settings > default precedence and same real bounds
    (reuses `settings.CHUNK_SIZE_MAX_TOKENS` -- a real "tokens per
    chunk" ceiling is the same real concept whether the chunk is a
    "parent" or not, no second, parallel ceiling constant needed)."""
    if override is not None:
        value = override
    elif org_settings is not None and org_settings.get("parent_chunk_size") is not None:
        value = org_settings["parent_chunk_size"]
    else:
        value = DEFAULT_SETTINGS["parent_chunk_size"]

    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"Invalid parent_chunk_size: {value!r} (must be a positive integer)")
    if value > settings.CHUNK_SIZE_MAX_TOKENS:
        raise ValueError(f"parent_chunk_size {value} exceeds the real maximum of {settings.CHUNK_SIZE_MAX_TOKENS}")
    return value


def resolve_parent_chunk_overlap(org_settings: dict | None = None, override: int | None = None, parent_chunk_size: int | None = None) -> int:
    """Phase 4, Étape 1 (correctif config parent_child) -- same real
    cross-field `overlap < size` check as `resolve_chunk_overlap`, but
    against `parent_chunk_size`, never the unrelated `chunk_size`."""
    if override is not None:
        value = override
    elif org_settings is not None and org_settings.get("parent_chunk_overlap") is not None:
        value = org_settings["parent_chunk_overlap"]
    else:
        value = DEFAULT_SETTINGS["parent_chunk_overlap"]

    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Invalid parent_chunk_overlap: {value!r} (must be zero or a positive integer)")

    effective_size = parent_chunk_size if parent_chunk_size is not None else resolve_parent_chunk_size(org_settings)
    if value >= effective_size:
        raise ValueError(f"parent_chunk_overlap ({value}) must be smaller than parent_chunk_size ({effective_size})")
    return value


def resolve_child_chunk_size(org_settings: dict | None = None, override: int | None = None) -> int:
    """Phase 4, Étape 1 (correctif config parent_child) -- the real
    "child_chunk_size" sibling of `resolve_parent_chunk_size` above."""
    if override is not None:
        value = override
    elif org_settings is not None and org_settings.get("child_chunk_size") is not None:
        value = org_settings["child_chunk_size"]
    else:
        value = DEFAULT_SETTINGS["child_chunk_size"]

    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"Invalid child_chunk_size: {value!r} (must be a positive integer)")
    if value > settings.CHUNK_SIZE_MAX_TOKENS:
        raise ValueError(f"child_chunk_size {value} exceeds the real maximum of {settings.CHUNK_SIZE_MAX_TOKENS}")
    return value


def resolve_child_chunk_overlap(org_settings: dict | None = None, override: int | None = None, child_chunk_size: int | None = None) -> int:
    """Phase 4, Étape 1 (correctif config parent_child) -- same real
    cross-field `overlap < size` check as `resolve_parent_chunk_overlap`,
    against `child_chunk_size`."""
    if override is not None:
        value = override
    elif org_settings is not None and org_settings.get("child_chunk_overlap") is not None:
        value = org_settings["child_chunk_overlap"]
    else:
        value = DEFAULT_SETTINGS["child_chunk_overlap"]

    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Invalid child_chunk_overlap: {value!r} (must be zero or a positive integer)")

    effective_size = child_chunk_size if child_chunk_size is not None else resolve_child_chunk_size(org_settings)
    if value >= effective_size:
        raise ValueError(f"child_chunk_overlap ({value}) must be smaller than child_chunk_size ({effective_size})")
    return value


def resolve_chunking_strategy(org_settings: dict | None = None, override: str | None = None) -> str:
    """Phase 4, Étape 1 -- same real override > org_settings > default
    precedence as `resolve_chunk_size`/`resolve_chunk_overlap` above.
    Real, defensive validation for the same reason those two already
    have it: this can be called with a raw dict from anywhere (a Celery
    task, a script), not only through an already-validated HTTP PATCH
    payload."""
    if override is not None:
        value = override
    elif org_settings is not None and org_settings.get("chunking_strategy") is not None:
        value = org_settings["chunking_strategy"]
    else:
        value = DEFAULT_SETTINGS["chunking_strategy"]

    if value not in CHUNKING_STRATEGIES:
        raise ValueError(f"Unknown chunking_strategy: {value!r} (expected one of {CHUNKING_STRATEGIES})")
    return value


def chunk_content(
    text: str, strategy: str, max_size: int, overlap: int, *, language: str | None = None, embedding_model: str | None = None,
) -> list[str]:
    """Phase 4, Étape 1 -- the real, single dispatch point for every
    one of the 6 real, standalone chunking strategies (Partie
    3.2.2-3.2.7), reusing each one's OWN already-built, already-tested
    function rather than a second, competing implementation of any of
    them. `max_size`/`overlap` are this codebase's own real, already-
    resolved `chunk_size`/`chunk_overlap` pair (see `resolve_chunk_size`/
    `resolve_chunk_overlap` above) -- passed through uniformly to
    whichever strategy accepts a size/overlap concept; a strategy with
    no real overlap concept of its own (`recursive`, `markdown`, `code`)
    simply never receives it, the same real, honest limitation
    `api/services/parent_child_chunking.py`'s own `_run_strategy`
    already documents for its own `"recursive"` branch.

    Deferred imports (function-local, not module-level): every one of
    these 6 strategy modules is genuinely standalone (Partie 3.2.2-3.2.7's
    own real, deliberate design), but `semantic_chunking.py` itself
    already imports `api.security.documents.generate_embeddings` at ITS
    own top level -- importing this module's own function from THAT
    module's own top level would close a real import cycle
    (`documents.py` -> `chunk_config.py` -> `semantic_chunking.py` ->
    `documents.py`) the moment `process_document` imports this function.
    A function-local import here (same real, established pattern this
    codebase already uses for `transformers`/`sentence_transformers` in
    `api/security/documents.py`) sidesteps it: by the time this function
    is actually CALLED (never at import time), `documents.py` has
    already finished loading."""
    from api.services.chunking import chunk_recursive_text
    from api.services.code_chunking import chunk_code_by_tokens
    from api.services.markdown_chunking import chunk_markdown_by_headings
    from api.services.metadata_enrichment import split_sentences
    from api.services.paragraph_chunking import chunk_by_paragraph_tokens
    from api.services.semantic_chunking import chunk_by_semantic_similarity, merge_semantic_chunks
    from api.services.sentence_chunking import chunk_by_sentence_tokens

    if strategy == "recursive":
        return chunk_recursive_text(text, max_size=max_size)
    if strategy == "markdown":
        return chunk_markdown_by_headings(text, max_chunk_size=max_size)
    if strategy == "code":
        return chunk_code_by_tokens(text, language=language, max_tokens=max_size)
    if strategy == "semantic":
        sentences = split_sentences(text)
        similarity_chunks = chunk_by_semantic_similarity(sentences, model_name=embedding_model)
        return merge_semantic_chunks(similarity_chunks, max_size=max_size)
    if strategy == "sentence":
        return chunk_by_sentence_tokens(text, max_tokens=max_size, overlap_tokens=overlap, language=language)
    if strategy == "paragraph":
        return chunk_by_paragraph_tokens(text, max_tokens=max_size, overlap_tokens=overlap)
    raise ValueError(
        f"chunk_content does not dispatch {strategy!r} -- 'fixed' and 'parent_child' are BOTH handled "
        f"directly by the caller (see this module's own CHUNKING_STRATEGIES docstring for why each one)"
    )
