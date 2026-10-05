"""api/services/policy_aware_retrieval.py -- real, additive filter
over item 13's own already-tested `check_policy`. Mocked at that clean
boundary -- this test module verifies the real filtering logic, never
re-tests OPA's own statistics/HTTP call (already covered by
tests/test_opa_policy.py)."""

from unittest.mock import AsyncMock, patch

from api.services.policy_aware_retrieval import filter_chunks_by_policy


def _chunk(chunk_id, metadata=None, document_id="doc-1"):
    return {"chunk_id": chunk_id, "document_id": document_id, "content": "text", "metadata_json": metadata or {}}


async def test_filter_chunks_by_policy_excludes_only_an_explicit_real_false():
    chunks = [_chunk("c1", {"department": "finance"}), _chunk("c2", {"department": "engineering"})]

    async def _fake_check_policy(input_data, package_path, rule_name):
        return input_data["resource"]["metadata"]["department"] != "finance"

    with patch("api.services.opa_policy.check_policy", AsyncMock(side_effect=_fake_check_policy)):
        result = await filter_chunks_by_policy(chunks, user_context={"user_id": "u1"})

    assert [c["chunk_id"] for c in result] == ["c2"]


async def test_filter_chunks_by_policy_never_excludes_on_none_fail_open():
    """Validation criterion: OPA disabled/unreachable (real `None` from
    check_policy) must never silently exclude a chunk a user was
    already authorized to see."""
    chunks = [_chunk("c1"), _chunk("c2")]

    with patch("api.services.opa_policy.check_policy", AsyncMock(return_value=None)):
        result = await filter_chunks_by_policy(chunks, user_context={"user_id": "u1"})

    assert [c["chunk_id"] for c in result] == ["c1", "c2"]


async def test_filter_chunks_by_policy_passes_real_chunk_metadata_and_user_context_as_opa_input():
    chunks = [_chunk("c1", {"region": "eu"}, document_id="doc-42")]
    mock_check_policy = AsyncMock(return_value=True)

    with patch("api.services.opa_policy.check_policy", mock_check_policy):
        await filter_chunks_by_policy(chunks, user_context={"user_id": "u1", "region": "eu"}, package_path="custom.pkg", rule_name="allowed")

    mock_check_policy.assert_awaited_once_with(
        {"user": {"user_id": "u1", "region": "eu"}, "resource": {"document_id": "doc-42", "metadata": {"region": "eu"}}},
        "custom.pkg", "allowed",
    )


async def test_filter_chunks_by_policy_with_an_empty_real_chunk_list():
    with patch("api.services.opa_policy.check_policy", AsyncMock()) as mock_check_policy:
        result = await filter_chunks_by_policy([], user_context={"user_id": "u1"})

    assert result == []
    mock_check_policy.assert_not_awaited()
