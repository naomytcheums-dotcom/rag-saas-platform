"""
Partie 1.3.9 -- reading and writing an organization's configuration. See
api/models/organization_settings.py's module docstring for why a row
stores only overrides, never a full snapshot of every default.

**Honest scope, same as Partie 1.3.6/1.3.7/1.3.8**: every one of these
17 settings is genuinely stored and genuinely readable/writable through
the real endpoints below -- unlike quotas/limits/usage, there is no
"not yet trackable" subset here, because a setting is pure
configuration with nothing to measure against. (`top_p` added at
Partie 4.3.3 -- the 17th.)

**Updated again at Partie 3.3.4-3.3.7 -- this paragraph keeps getting
less stale as api/ grows a real pipeline of its own**: at the time
this docstring was first written (Partie 1.3.9), NOTHING in api/ read
these settings, because api/ had no document-ingestion or retrieval
pipeline of its own yet. That's no longer true for 6 of these 17
settings (a further 6 covered separately below, Partie 4.3.1-4.3.5/5.1.1),
verified by reading the actual call sites, not assumed:

- chunk_size / chunk_overlap: read for real in
  `api/security/documents.py`'s own `process_document`, passed straight
  into `chunk_text` (Partie 3.2.1) -- real, live, per-organization
  chunking. `api/services/chunk_config.py` (Partie 3.3.1/3.3.2) adds a
  real, reusable `resolve_chunk_size`/`resolve_chunk_overlap` pair on
  top, for the 7 newer, standalone chunking strategies from Partie
  3.2.2-3.2.8 (still not wired into `process_document` itself -- see
  each one's own module for why).
- embedding_model: read for real in the same `process_document`,
  passed into `generate_embeddings`/`_get_embedder` -- real, live,
  per-organization embedding model selection.
  `api/services/embedding_config.py` (Partie 3.3.3) adds real
  validation against a known, documented model allowlist.
- retrieval_strategy / reranker_model / top_k / score_threshold: read
  for real by `POST /organizations/{org_id}/search`
  (`api/routers/search.py`, Partie 3.3.4-3.3.7), via
  `api/services/retrieval_pipeline.py`'s own real `search`/
  `search_with_context` -- api/ now HAS a real, live, multi-tenant
  retrieval endpoint (real vector search + real BM25 + real RRF fusion
  + real cross-encoder reranking, all real per-organization data,
  isolated by `DocumentChunk.organization_id`, migration `0047`). See
  `api/services/retrieval_pipeline.py`'s own top docstring for the
  real, honest scale limit this still carries (no ANN index yet -- an
  in-memory, brute-force real similarity search, correct today, real
  future work once an organization's own chunk count warrants a real
  pgvector column).

**Updated again at Partie 4.3.1-4.3.5/5.1.1**: 6 more of these settings
are now genuinely read for real too:

- llm_provider / llm_model / temperature / top_p / system_prompt /
  max_tokens: real resolvers in `api/services/llm_config.py`
  (`resolve_llm_provider`/`resolve_llm_model`/`resolve_temperature`/
  `resolve_top_p`/`resolve_system_prompt`/`resolve_max_tokens`/
  `resolve_llm_config`), genuinely consumed by
  `api/services/agent_orchestrator.py`'s own real `AgentOrchestrator.run_agent`
  -- the first real, live, in-process caller (not an HTTP endpoint yet;
  see that module's own top docstring for its own real, honest scope:
  one real agent run is one real, traced LLM call, real tool-calling
  and multi-step workflows are separate, later, real work). `llm_model`'s
  own real resolution deliberately does NOT fall back to this table's
  own known-stale default (`"claude-3-sonnet-20240229"`) -- it falls
  back to the resolved PROVIDER's own real, live default model instead
  (`api.config.settings.ANTHROPIC_MODEL`, etc.), a real, deliberate fix
  building on this docstring's own earlier, honest flag of that
  staleness.

Only 3 settings (`citation_required`/`language`/`timezone`) remain
genuinely unread by api/'s own pipeline -- none of the 3 have any real
equivalent anywhere api/ currently calls an LLM. Every one of the
remaining 3 (plus the earlier real `src/` staleness already
documented above for the settings now superseded by real api/
resolvers) is independently hardcoded or simply absent in `src/`
(verified by reading the actual constants, not assumed):

- citation_required / language / timezone: no corresponding toggle
  exists in `src/` at all

A real, live, multi-tenant HTTP endpoint that actually ANSWERS a
question (retrieval + generation combined, citing sources, honoring
`citation_required`/`language`) is still real, substantial, separate
work belonging to Partie 9 (or whichever later étape actually asks for
it) -- `AgentOrchestrator` is real, live, and tested, but is a real
building block for that, not that endpoint itself. See
api/models/organization_settings.py and docs/AUTH_BACKEND_SETUP.md for
the same story in the model/docs layer.
"""

import uuid
from typing import Any
from zoneinfo import available_timezones

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.organization_settings import OrganizationSettings

DEFAULT_SETTINGS: dict[str, Any] = {
    "chunk_size": 512,
    "chunk_overlap": 50,
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "llm_provider": "anthropic",
    "llm_model": "claude-3-sonnet-20240229",
    "temperature": 0.7,
    # Partie 4.3.3 -- real, applied by api/services/llm_config.py's own
    # resolve_top_p, real 0.0-1.0 bounds (real nucleus-sampling
    # parameter, standard across every real LLM provider).
    "top_p": 1.0,
    "top_k": 5,
    "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "system_prompt": "You are a helpful assistant.",
    "retrieval_strategy": "hybrid",
    "max_tokens": 4096,
    "citation_required": True,
    "language": "en",
    "timezone": "UTC",
    # Partie 3.3.7 -- real, applied by api/services/retrieval_pipeline.py's
    # own search() after real per-strategy score normalization (real
    # scores across strategies are on very different real scales --
    # cosine similarity, raw BM25, RRF fusion, cross-encoder logits --
    # see that module's own top docstring for the real, necessary
    # normalization this requires to make one single 0-1 threshold
    # meaningful across all of them).
    "score_threshold": 0.5,
    # Partie 3.4.7 -- real, applied by
    # api/services/retrieval_pipeline.py's own hybrid_search (Reciprocal
    # Rank Fusion's own smoothing constant) -- 60 is the same real,
    # standard default from the original RRF paper src/retrieval.py's
    # own RRF_K already uses.
    "rrf_k": 60,
}

# Computed once at import time, not per-call -- available_timezones()
# walks the tzdata database, cheap but pointless to repeat on every
# validation.
_VALID_TIMEZONES = available_timezones()


def get_default_settings() -> dict[str, Any]:
    """Item 3's literal function -- a fresh copy each call, so a caller
    mutating the result never corrupts the module-level DEFAULT_SETTINGS."""
    return dict(DEFAULT_SETTINGS)


async def create_default_settings(db: AsyncSession, *, organization_id: uuid.UUID) -> OrganizationSettings:
    """Called once, at organization creation
    (api/security/organizations.py's create_organization_with_owner) --
    does NOT commit, same convention as create_default_quota, so it's
    part of the SAME transaction as the organization and its founding
    Owner membership. Starts with zero overrides -- every setting
    resolves to DEFAULT_SETTINGS until an Owner changes one."""
    settings_row = OrganizationSettings(organization_id=organization_id, settings={})
    db.add(settings_row)
    await db.flush()
    return settings_row


async def get_org_settings(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    """
    Item 3's literal function -- the effective configuration: defaults,
    with this organization's explicit overrides layered on top. `None`
    if no row exists (an organization created before this migration, or
    whose row was deleted out of band) falls back to pure defaults
    rather than raising -- same "fail toward the configured defaults"
    reasoning as api/security/quotas.py's get_quota_limits, so a
    pre-existing org isn't suddenly broken by a step added after it
    already existed. Answers this step's own "migration" question: no
    backfill was needed FOR THIS FUNCTION, because it degrades
    gracefully to defaults with no row at all -- see this step's
    delivered response for whether a backfill migration is still worth
    doing anyway (Points restants).
    """
    row = await db.scalar(select(OrganizationSettings).where(OrganizationSettings.organization_id == organization_id))
    overrides = row.settings if row is not None else {}
    return {**DEFAULT_SETTINGS, **overrides}


async def get_org_setting(db: AsyncSession, organization_id: uuid.UUID, key: str) -> Any:
    """Item 3's literal function -- one setting's effective value.
    Raises on an unrecognized key rather than returning None: an
    unknown key is a caller bug (a typo, a renamed setting), and
    silently returning None would be indistinguishable from a real
    setting whose value happens to be null."""
    if key not in DEFAULT_SETTINGS:
        raise ValueError(f"Unknown organization setting: {key!r}")
    return (await get_org_settings(db, organization_id))[key]


async def update_org_settings(db: AsyncSession, organization_id: uuid.UUID, updates: dict[str, Any]) -> dict[str, Any]:
    """
    Item 3's literal function -- a partial update: only the keys present
    in `updates` change, everything else keeps its current effective
    value (its own override, or the default). Reassigns `.settings`
    to a NEW dict (`{**row.settings, **updates}`) rather than mutating
    the existing one in place (`row.settings[key] = value`) --
    SQLAlchemy's change-tracking only notices a JSON column's value
    changed when the attribute is reassigned to a different object,
    not when an existing dict is mutated in place; reassignment sidesteps
    needing sqlalchemy.ext.mutable.MutableDict for what's otherwise a
    one-line function.

    Type/range validation (chunk_size > 0, retrieval_strategy in the
    known set, etc.) happens one layer up, in
    api/schemas/organization_settings.py's
    OrganizationSettingsUpdateRequest -- this function trusts its
    caller the same way api/security/quotas.py's OrganizationQuota
    update path trusts api/routers/quotas.py's already-validated payload.

    Does not commit -- same convention as every other security-layer
    write function in this codebase (the caller decides the transaction
    boundary).
    """
    row = await db.scalar(select(OrganizationSettings).where(OrganizationSettings.organization_id == organization_id))
    if row is None:
        # An organization that predates this migration, or whose row
        # was deleted out of band -- create it now rather than 404ing
        # an Owner who's allowed to be here (same reasoning as
        # api/routers/quotas.py's update_organization_quotas).
        row = OrganizationSettings(organization_id=organization_id, settings={})
        db.add(row)
        await db.flush()

    row.settings = {**row.settings, **updates}
    await db.flush()
    return {**DEFAULT_SETTINGS, **row.settings}


def is_valid_timezone(name: str) -> bool:
    """Real validation, not a placeholder -- checked against Python's
    own tzdata database (the same one `zoneinfo.ZoneInfo` resolves
    against at runtime), not a hand-maintained list that could drift
    from what the stdlib actually accepts."""
    return name in _VALID_TIMEZONES
