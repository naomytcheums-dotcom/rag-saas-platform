"""
api/services/mem0_service.py -- `Memory.add`/`Memory.search` make real
LLM calls under the hood (mem0's own automatic fact extraction, via
litellm) -- same real, documented exception as every other real,
paid-LLM-call module in this codebase (tests/test_llm_providers.py's
own docstring). Tests here prove the real, verifiable part: this
module builds a real `MemoryConfig` wired to THIS codebase's own real,
resolved provider/model/embedding, using the exact import paths and
config shapes verified directly against the installed `mem0ai` package
before writing this module -- never guessed.
"""

import uuid
from unittest.mock import AsyncMock

from mem0.configs.base import MemoryConfig

import api.services.mem0_service as mem0_service
from api.services.mem0_service import _collection_name, get_memory


def test_collection_name_is_real_and_unique_per_organization_and_agent():
    org_a, org_b, agent = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    name_a = _collection_name(org_a, agent)
    name_b = _collection_name(org_b, agent)

    assert name_a != name_b
    assert "-" not in name_a  # real Qdrant collection name constraint


async def test_get_memory_builds_a_real_config_wired_to_this_codebases_own_provider(monkeypatch, tmp_path):
    """Validation criterion: mem0 must run against THIS organization's
    own real, configured LLM provider -- never mem0's own independent
    OpenAI default."""
    monkeypatch.setattr("api.services.mem0_service._STORAGE_ROOT", tmp_path)
    # `llm_providers.py` does `from api.config import settings` at import
    # time, so replacing `api.config.settings` wholesale never reaches
    # the name already bound in that module -- patch the real object's
    # attributes instead (same discipline as tests/test_llm_providers.py).
    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    org_id, agent_id = uuid.uuid4(), uuid.uuid4()
    memory = await get_memory(org_id, agent_id, "anthropic", "claude-3-5-sonnet-20241022", "sentence-transformers/all-MiniLM-L6-v2")

    assert memory.llm.config.model == "claude-3-5-sonnet-20241022"
    assert memory.llm.config.api_key == "sk-ant-test"
    assert memory.embedding_model.config.model == "sentence-transformers/all-MiniLM-L6-v2"


async def test_delete_user_memories_calls_the_real_mem0_delete_all_scoped_to_one_user(monkeypatch):
    """Hardening Mission, Phase 6 -- REGRESSION for a real, confirmed
    audit gap: this module had `add_memory`/`search_memory` but NO
    delete function at all. Mocked at `get_memory` itself (never loads a
    real embedding model) -- the real thing under test is that
    `delete_user_memories` calls mem0's own real `Memory.delete_all`
    with exactly the right `user_id`, never another user's."""
    fake_memory = type("FakeMemory", (), {"delete_all": lambda self, **kw: calls.append(kw)})()
    calls = []
    monkeypatch.setattr(mem0_service, "get_memory", AsyncMock(return_value=fake_memory))

    org_id, agent_id = uuid.uuid4(), uuid.uuid4()
    await mem0_service.delete_user_memories(org_id, agent_id, "user-42", "anthropic", "claude-3-5-sonnet-20241022", "sentence-transformers/all-MiniLM-L6-v2")

    assert calls == [{"user_id": "user-42"}]


async def test_purge_agent_memory_resets_and_removes_the_real_working_directory(monkeypatch, tmp_path):
    """Real, full per-(organization, agent) purge: mem0's own reset()
    called, the on-disk working dir actually removed, cache evicted."""
    monkeypatch.setattr(mem0_service, "_STORAGE_ROOT", tmp_path)
    org_id, agent_id = uuid.uuid4(), uuid.uuid4()
    working_dir = tmp_path / str(org_id) / str(agent_id)
    working_dir.mkdir(parents=True)
    (working_dir / "history.db").write_text("real fake data")

    reset_calls = []
    fake_memory = type("FakeMemory", (), {"reset": lambda self: reset_calls.append(True)})()
    monkeypatch.setattr(mem0_service, "get_memory", AsyncMock(return_value=fake_memory))
    mem0_service._INSTANCES[(org_id, agent_id)] = fake_memory

    await mem0_service.purge_agent_memory(org_id, agent_id, "anthropic", "claude-3-5-sonnet-20241022", "sentence-transformers/all-MiniLM-L6-v2")

    assert reset_calls == [True]
    assert not working_dir.exists()
    assert (org_id, agent_id) not in mem0_service._INSTANCES


async def test_purge_organization_memory_removes_every_real_agent_directory_for_that_org_only(tmp_path, monkeypatch):
    """Real, organization-wide purge used by the account/organization
    deletion cascade -- must never touch a DIFFERENT organization's own
    real directory."""
    monkeypatch.setattr(mem0_service, "_STORAGE_ROOT", tmp_path)
    org_a, org_b, agent = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    (tmp_path / str(org_a) / str(agent)).mkdir(parents=True)
    (tmp_path / str(org_b) / str(agent)).mkdir(parents=True)
    mem0_service._INSTANCES[(org_a, agent)] = object()

    await mem0_service.purge_organization_memory(org_a)

    assert not (tmp_path / str(org_a)).exists()
    assert (tmp_path / str(org_b)).exists()
    assert (org_a, agent) not in mem0_service._INSTANCES


async def test_purge_organization_memory_is_a_real_no_op_for_an_organization_with_no_memory_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(mem0_service, "_STORAGE_ROOT", tmp_path)
    await mem0_service.purge_organization_memory(uuid.uuid4())  # must not raise


# A real "two live Memory() instances in one process" test is
# deliberately NOT written here -- found for real while writing this
# test suite, not assumed: qdrant-client's own real LOCAL-mode storage
# takes an exclusive file lock on a FIXED, shared path
# (`~/.mem0/migrations_qdrant`, mem0's own internal bookkeeping,
# entirely separate from this module's own per-organization
# `VectorStoreConfig.path`) -- a second real `Memory()` instantiated
# in the SAME process while the first is still alive raises a real
# `RuntimeError` from qdrant-client itself ("already accessed by
# another instance ... use Qdrant server instead"). This is a real
# constraint of mem0's own local-mode architecture, not a bug in this
# module's own per-organization isolation (proven separately by
# `test_collection_name_is_real_and_unique_per_organization_and_agent`
# above) -- see ROADMAP.md's own entry for this étape for the real
# production implication (a real Qdrant server, not local mode, is
# required for genuine concurrent multi-tenant use).
