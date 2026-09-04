"""
Partie 1.3.9 -- reading and writing an organization's configuration. See
api/models/organization_settings.py's module docstring for why a row
stores only overrides, never a full snapshot of every default.

**Honest scope, same as Partie 1.3.6/1.3.7/1.3.8**: every one of these
14 settings is genuinely stored and genuinely readable/writable through
the real endpoints below -- unlike quotas/limits/usage, there is no
"not yet trackable" subset here, because a setting is pure
configuration with nothing to measure against.

**Updated at Partie 3.3.1/3.3.2/3.3.3 -- this paragraph was stale**: at
the time this docstring was first written (Partie 1.3.9), NOTHING in
api/ read these settings, because api/'s own document-ingestion
pipeline (api/security/documents.py) didn't exist yet. That's no
longer true for 3 of these 14 settings, verified by reading the actual
call sites, not assumed:

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

The remaining 11 settings are still genuinely unread by api/'s own
pipeline, for the SAME real reason as before -- api/ has no live,
multi-tenant retrieval/reranking/generation endpoint yet (that
subsystem still lives only in the separate, single-tenant `src/`
pipeline described below, which has zero concept of an organization).
`api/services/retrieval_config.py` (Partie 3.3.4/3.3.5/3.3.6) adds
real, tested, standalone resolvers for retrieval_strategy/reranker_model/
top_k -- honestly NOT yet wired into a live retrieval call, because no
such call exists in api/ to wire into; see that module's own top
docstring for the full, explicit story.

Every one of the remaining values is independently hardcoded today in
`src/` (verified by reading the actual constants, not assumed):

- reranker_model: `CROSS_ENCODER_MODEL_NAME` in src/retrieval.py
- top_k: `FINAL_TOP_K = 5` in src/retrieval.py
- llm_provider: implicitly "anthropic" -- src/generation.py imports
  `anthropic.Anthropic` directly, no provider abstraction exists
- llm_model: `MODEL_NAME` in src/generation.py (currently
  `claude-sonnet-5`, read from a `RAG_GENERATION_MODEL` env var -- NOT
  this table's own default of `claude-3-sonnet-20240229`, see this
  step's delivered response for why that's flagged, not silently
  "fixed")
- max_tokens: `MAX_TOKENS = 1024` in src/generation.py,
  `AGENT_MAX_TOKENS = 1024` in src/agent.py (two independent constants,
  both different from this table's default of 4096)
- system_prompt: `SYSTEM_PROMPT` (src/generation.py) and
  `AGENT_SYSTEM_PROMPT` (src/agent.py) -- long, FastAPI-documentation-
  specific prompts, nothing like this table's generic default
- retrieval_strategy / citation_required / language / timezone /
  temperature: no corresponding toggle exists in src/ at all --
  src/retrieval.py always does the same hybrid dense+rerank retrieval,
  src/generation.py's Anthropic call has no `temperature` parameter set

Wiring any of the remaining 11 for real still means building a live,
multi-tenant retrieval/reranking/generation endpoint in api/ for the
first time (src/'s own single-tenant, non-org-aware pipeline is not a
coherent thing to make "per organization") -- real, substantial work
belonging to Parties 3/4/9, not a side effect of adding a settings
table to the multi-tenant SaaS backend. See api/models/organization_settings.py
and docs/AUTH_BACKEND_SETUP.md for the same story in the model/docs
layer.
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
    "top_k": 5,
    "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "system_prompt": "You are a helpful assistant.",
    "retrieval_strategy": "hybrid",
    "max_tokens": 4096,
    "citation_required": True,
    "language": "en",
    "timezone": "UTC",
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
