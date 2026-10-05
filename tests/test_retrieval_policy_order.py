"""Hardening Mission, §8 -- order of the retrieval pipeline stages around the
access policy. The policy filter used to run AFTER MMR, the score threshold and
the cut to top_k: a restricted user got fewer results than permitted chunks
existed, and MMR picked its "diverse" subset while still seeing chunks the
caller may not read (their mere presence changed which permitted chunks were
returned). The strategy function and the policy filter are stubbed at their own
tested boundaries; the ordering/over-fetch logic in `search()` is the real code."""

from unittest.mock import AsyncMock

from api.services import retrieval_pipeline as rp

POLICY_ON = {"policy_aware_retrieval_enabled": True, "score_threshold": 0.0}


def _chunks(n: int) -> list[dict]:
    return [{"chunk_id": f"c{i}", "content": f"text {i}", "score": 1.0 - i / 100, "embedding": [1.0, 0.0]} for i in range(n)]


def _install_fake_strategy(monkeypatch, forbidden: set[str]):
    """A strategy that returns `top_k` ranked chunks (c0 best), plus a policy
    filter that removes `forbidden` ids. Returns the list of top_k values asked for."""
    asked: list[int] = []

    async def fake_strategy(db, organization_id, query, top_k=None, org_settings=None, **kwargs):
        asked.append(top_k)
        return _chunks(top_k)

    async def fake_policy(chunks, user_context):
        return [c for c in chunks if c["chunk_id"] not in forbidden]

    monkeypatch.setitem(rp._STRATEGY_FUNCTIONS, "vector_only", fake_strategy)
    monkeypatch.setattr("api.services.policy_aware_retrieval.filter_chunks_by_policy", fake_policy)
    return asked


async def test_a_restricted_user_is_backfilled_up_to_top_k_from_the_wider_candidate_pool(db_session, monkeypatch):
    asked = _install_fake_strategy(monkeypatch, forbidden={"c0", "c1"})

    results = await rp.search(db_session, "org", "refunds", top_k=3, strategy="vector_only", org_settings=POLICY_ON, user_context={"user_id": "u1"})

    assert asked == [3 * rp.app_settings.POLICY_OVERFETCH_FACTOR]  # a wider pool was fetched
    assert [r["chunk_id"] for r in results] == ["c2", "c3", "c4"]  # still a full page, best permitted first


async def test_the_final_page_never_exceeds_top_k(db_session, monkeypatch):
    _install_fake_strategy(monkeypatch, forbidden=set())

    results = await rp.search(db_session, "org", "refunds", top_k=3, strategy="vector_only", org_settings=POLICY_ON, user_context={"user_id": "u1"})

    assert [r["chunk_id"] for r in results] == ["c0", "c1", "c2"]


async def test_without_a_user_context_nothing_changes_no_over_fetch_no_filter(db_session, monkeypatch):
    asked = _install_fake_strategy(monkeypatch, forbidden={"c0"})

    results = await rp.search(db_session, "org", "refunds", top_k=3, strategy="vector_only", org_settings=POLICY_ON)

    assert asked == [3]
    assert [r["chunk_id"] for r in results] == ["c0", "c1", "c2"]  # policy not applied: no caller identity


async def test_the_policy_is_applied_before_mmr_so_mmr_never_sees_a_forbidden_chunk(db_session, monkeypatch):
    _install_fake_strategy(monkeypatch, forbidden={"c0", "c1"})
    seen_by_mmr: list[list[str]] = []

    def fake_mmr(candidates, query_embedding, lambda_param, top_k):
        seen_by_mmr.append([c["chunk_id"] for c in candidates])
        return candidates[:top_k]

    monkeypatch.setattr("api.services.mmr.select_diverse_chunks", fake_mmr)
    monkeypatch.setattr("api.services.semantic_filtering.compute_query_embedding", lambda query, org_settings=None: [1.0, 0.0])

    results = await rp.search(
        db_session, "org", "refunds", top_k=3, strategy="vector_only", user_context={"user_id": "u1"},
        org_settings={**POLICY_ON, "mmr_enabled": True},
    )

    assert seen_by_mmr and not ({"c0", "c1"} & set(seen_by_mmr[0]))
    assert [r["chunk_id"] for r in results] == ["c2", "c3", "c4"]


async def test_an_empty_policy_result_returns_nothing_rather_than_leaking_a_forbidden_chunk(db_session, monkeypatch):
    _install_fake_strategy(monkeypatch, forbidden={f"c{i}" for i in range(30)})

    results = await rp.search(db_session, "org", "refunds", top_k=3, strategy="vector_only", org_settings=POLICY_ON, user_context={"user_id": "u1"})

    assert results == []
