"""
Real, automatic conversational memory via mem0 (Apache 2.0) --
genuinely NEW capability, not a duplicate of this codebase's own
already-real agent memory (`api/models/agent_memory.py`'s short-term
`AgentMemoryItem`, `api/models/agent_long_term_memory.py`'s long-term
`AgentLongTermMemoryItem`): both of those are real, manual key-value
stores -- a caller decides what `key`/`value` to persist. mem0's own
real value is automatic extraction (an LLM decides what's worth
remembering from a real conversation) plus semantic, vector-based
retrieval -- a different, complementary capability, not the same
thing rebuilt with a new library (the same "is this genuinely new or
a duplicate" judgment this étape already applied to Ragas/DeepEval).

**Wired to this codebase's OWN real LLM/embedding stack**:
`llm=LlmConfig(provider="litellm", ...)` reuses
`api.services.llm_providers._provider_kwargs`'s own real, resolved
`model`/`api_key` for whichever provider an organization has actually
configured -- never mem0's own independent OpenAI default.
`embedder=EmbedderConfig(provider="huggingface", ...)` uses the same
real, local `embedding_model` an organization already has configured
(api/security/organization_settings.py), with its real, probed
dimension (same "never guess a dimension" discipline as
api/services/graph_rag.py's own `get_lightrag`).

**Storage**: mem0's own default Qdrant backend, in real LOCAL/on-disk
mode (`path=`, no server) -- verified directly against the installed
package's own real default (`QdrantConfig(path='/tmp/qdrant', host=None,
port=None)`) -- no new infrastructure dependency, same "no new server
for this étape's own real scope" discipline as
api/services/graph_rag.py's own file-based LightRAG storage. Real,
per-(organization, agent) isolation via a distinct Qdrant collection
name and on-disk path -- never a shared collection two organizations'
memories could leak across.
"""

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_INSTANCES: dict[tuple[uuid.UUID, uuid.UUID], object] = {}

_STORAGE_ROOT = Path("storage") / "mem0"


def close_all_memories() -> None:
    """Release cached local clients before Python tears down its import machinery."""
    closed_clients: set[int] = set()
    try:
        for memory in list(_INSTANCES.values()):
            for name in ("vector_store", "_telemetry_vector_store", "_entity_store"):
                store = getattr(memory, name, None)
                if store is None or not getattr(store, "is_local", False):
                    continue
                client = getattr(store, "client", None)
                if client is None or id(client) in closed_clients:
                    continue
                closed_clients.add(id(client))
                try:
                    client.close()
                except Exception as exc:
                    logger.warning("close_all_memories: local %s client close failed (%s)", name, type(exc).__name__)
            close = getattr(memory, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    logger.warning("close_all_memories: memory close failed (%s)", type(exc).__name__)
    finally:
        _INSTANCES.clear()


class Mem0NotAvailableError(Exception):
    """Same honest-degradation contract as
    api/services/graph_rag.py's own GraphRAGNotAvailableError."""


def _collection_name(organization_id: uuid.UUID, agent_id: uuid.UUID) -> str:
    # Qdrant collection names are real, constrained identifiers -- a
    # plain hyphenated UUID pair is real and unique per (org, agent),
    # never colliding across organizations.
    return f"mem0_{organization_id}_{agent_id}".replace("-", "")


async def get_memory(organization_id: uuid.UUID, agent_id: uuid.UUID, llm_provider: str, llm_model: str, embedding_model: str):
    """Real, cached, per-(organization, agent) mem0 `Memory` instance --
    building one loads a real embedding model, same "load once, cache"
    reasoning as api/services/graph_rag.py's own `get_lightrag`."""
    key = (organization_id, agent_id)
    if key in _INSTANCES:
        return _INSTANCES[key]

    import os

    # Real, deliberate opt-out -- mem0's own `MEM0_TELEMETRY` env var is
    # read at MODULE IMPORT time (verified in the installed package's
    # own `mem0/memory/telemetry.py`, defaults `True`), so it must be
    # set BEFORE mem0 is ever imported anywhere in this process.
    # Sending anonymous usage data to a third party (PostHog) by
    # default is inconsistent with every other real privacy/security
    # discipline in this codebase (PII masking, secret redaction in
    # traces) -- `setdefault` so an operator who explicitly wants it
    # back on can still set the real env var themselves.
    os.environ.setdefault("MEM0_TELEMETRY", "False")

    try:
        from mem0 import Memory
        from mem0.configs.base import MemoryConfig
        from mem0.embeddings.configs import EmbedderConfig
        from mem0.llms.configs import LlmConfig
        from mem0.vector_stores.configs import VectorStoreConfig
    except ImportError as exc:
        raise Mem0NotAvailableError(f"mem0ai is not installed: {exc}") from exc

    from api.security.documents import generate_embeddings
    from api.services.llm_providers import _provider_kwargs

    llm_kwargs = _provider_kwargs(llm_provider, llm_model)
    embedding_dim = len(generate_embeddings(["dimension probe"], embedding_model)[0])

    working_dir = _STORAGE_ROOT / str(organization_id) / str(agent_id)
    working_dir.mkdir(parents=True, exist_ok=True)

    config = MemoryConfig(
        llm=LlmConfig(provider="litellm", config={"model": llm_kwargs["model"], "api_key": llm_kwargs.get("api_key")}),
        embedder=EmbedderConfig(provider="huggingface", config={"model": embedding_model, "embedding_dims": embedding_dim}),
        vector_store=VectorStoreConfig(
            provider="qdrant",
            config={"collection_name": _collection_name(organization_id, agent_id), "path": str(working_dir), "embedding_model_dims": embedding_dim},
        ),
        history_db_path=str(working_dir / "history.db"),
    )
    memory = Memory(config)
    _INSTANCES[key] = memory
    return memory


async def add_memory(
    organization_id: uuid.UUID, agent_id: uuid.UUID, user_id: str, messages: list[dict],
    llm_provider: str, llm_model: str, embedding_model: str,
) -> dict:
    """Real, automatic extraction -- mem0's own real LLM call decides
    what from `messages` is worth remembering, never a manual
    key/value this codebase's own AgentLongTermMemoryItem already
    requires a caller to decide."""
    memory = await get_memory(organization_id, agent_id, llm_provider, llm_model, embedding_model)
    return memory.add(messages, user_id=user_id)


async def search_memory(
    organization_id: uuid.UUID, agent_id: uuid.UUID, user_id: str, query: str,
    llm_provider: str, llm_model: str, embedding_model: str, limit: int = 5,
) -> list[dict]:
    """Real, semantic (vector) retrieval -- finds memories relevant to
    `query` by meaning, not by an exact key lookup."""
    memory = await get_memory(organization_id, agent_id, llm_provider, llm_model, embedding_model)
    result = memory.search(query, user_id=user_id, limit=limit)
    return result.get("results", result) if isinstance(result, dict) else result


async def delete_user_memories(
    organization_id: uuid.UUID, agent_id: uuid.UUID, user_id: str, llm_provider: str, llm_model: str, embedding_model: str,
) -> None:
    """Hardening Mission, Phase 6 -- the real, confirmed-missing deletion
    half of this module: an external audit found `add_memory`/`search_memory`
    but NO delete function at all anywhere in this file -- a genuine
    GDPR/right-to-be-forgotten gap the moment this real, working feature
    is ever wired to a real caller (today it has zero -- see this
    module's own docstring; `api/security/documents.py`'s own
    `permanent_delete_document` calls this per the SAME real
    docstring's own GDPR requirement regardless, so a FUTURE wiring of
    mem0 into a real agent conversation never silently reintroduces this
    gap). Uses mem0's own real `Memory.delete_all(user_id=...)` -- the
    one real user's own memories within this (organization, agent)
    scope, never another user's."""
    memory = await get_memory(organization_id, agent_id, llm_provider, llm_model, embedding_model)
    memory.delete_all(user_id=user_id)


async def purge_agent_memory(organization_id: uuid.UUID, agent_id: uuid.UUID, llm_provider: str, llm_model: str, embedding_model: str) -> None:
    """Hardening Mission, Phase 6 -- the real, full, per-(organization,
    agent) purge: mem0's own real `Memory.reset()` wipes every real
    memory in this scope's own real, isolated Qdrant collection (never
    another organization's -- see this module's own top docstring on
    per-(organization, agent) isolation), then the real on-disk
    `working_dir` itself is removed (mem0's own `reset()` does not
    delete its own history/config files on disk, verified directly
    against the installed package) and the cached instance is evicted
    so a later real call rebuilds a genuinely fresh one rather than
    reusing a `Memory` object bound to a now-deleted collection."""
    import shutil

    memory = await get_memory(organization_id, agent_id, llm_provider, llm_model, embedding_model)
    memory.reset()
    _INSTANCES.pop((organization_id, agent_id), None)
    working_dir = _STORAGE_ROOT / str(organization_id) / str(agent_id)
    shutil.rmtree(working_dir, ignore_errors=True)


async def purge_organization_memory(organization_id: uuid.UUID) -> None:
    """Hardening Mission, Phase 6 -- a real, organization-wide purge for
    every real agent this organization ever had memory for, without
    needing each one's own `llm_provider`/`llm_model`/`embedding_model`
    (a real cached `Memory` instance isn't needed to delete a real,
    already-isolated on-disk directory tree -- `reset()` above is only
    necessary to also clear mem0's own in-process Qdrant client state
    for an ALREADY-CACHED instance; a cold, never-instantiated agent has
    no such state to clear). Used by `api/tasks/account_purge.py`'s own
    real organization-deletion cascade, the same real "no copy of a
    deleted organization's data survives anywhere" requirement that
    cascade already enforces for every other real store."""
    import shutil

    org_dir = _STORAGE_ROOT / str(organization_id)
    if not org_dir.exists():
        return
    for agent_dir in org_dir.iterdir():
        try:
            agent_id = uuid.UUID(agent_dir.name)
        except ValueError:
            continue
        _INSTANCES.pop((organization_id, agent_id), None)
    shutil.rmtree(org_dir, ignore_errors=True)
