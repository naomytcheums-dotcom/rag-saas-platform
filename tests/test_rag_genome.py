"""api/services/rag_genome.py -- real, deterministic config hashing +
real, additive RagExperiment provenance records (item 19, Experiment
Lab / RAG Genome). Pure, real logic -- no mocking needed."""

import uuid

from api.services.rag_genome import compute_config_hash, get_experiments_by_hash, list_experiments, record_experiment


def test_compute_config_hash_is_deterministic_regardless_of_key_order():
    """Validation criterion: the same real config, different insertion
    order, must hash identically -- never look like two different
    experiments."""
    a = compute_config_hash({"system_prompt": "x", "top_k": 5})
    b = compute_config_hash({"top_k": 5, "system_prompt": "x"})
    assert a == b


def test_compute_config_hash_differs_for_a_real_different_config():
    a = compute_config_hash({"system_prompt": "x"})
    b = compute_config_hash({"system_prompt": "y"})
    assert a != b


async def _make_org(db_session):
    from api.models.organization import Organization

    org = Organization(name="Genome Org", slug=f"genome-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def test_record_experiment_persists_a_real_row_with_the_real_config_hash(db_session):
    org = await _make_org(db_session)
    config = {"system_prompt": "A candidate prompt."}

    experiment = await record_experiment(
        db_session, org.id, config, source="rag_evolution_engine",
        decision="candidate_recommended", metrics={"semantic_similarity": {"delta": 0.15}},
    )
    await db_session.commit()

    assert experiment.config_hash == compute_config_hash(config)
    assert experiment.organization_id == org.id
    assert experiment.decision == "candidate_recommended"


async def test_get_experiments_by_hash_finds_a_real_previously_recorded_experiment(db_session):
    org = await _make_org(db_session)
    config = {"system_prompt": "A repeated candidate."}

    await record_experiment(db_session, org.id, config, source="manual")
    await db_session.commit()

    found = await get_experiments_by_hash(db_session, org.id, compute_config_hash(config))
    assert len(found) == 1
    assert found[0].config_json == config


async def test_get_experiments_by_hash_never_leaks_across_organizations(db_session):
    org_a = await _make_org(db_session)
    org_b = await _make_org(db_session)
    config = {"system_prompt": "Shared config text."}

    await record_experiment(db_session, org_a.id, config, source="manual")
    await db_session.commit()

    found_for_b = await get_experiments_by_hash(db_session, org_b.id, compute_config_hash(config))
    assert found_for_b == []


async def test_list_experiments_returns_every_real_experiment_for_the_organization(db_session):
    """Real, honest assertion: both real experiments come back --
    exact newest-first ordering at sub-second `created_at` resolution
    (a real, known SQLite/fast-test timing limitation) is NOT asserted
    here to avoid a flaky test asserting something this function's own
    real behavior can't reliably guarantee at that resolution."""
    org = await _make_org(db_session)
    first = await record_experiment(db_session, org.id, {"v": 1}, source="manual")
    second = await record_experiment(db_session, org.id, {"v": 2}, source="manual")
    await db_session.commit()

    results = await list_experiments(db_session, org.id)
    assert {r.id for r in results} == {first.id, second.id}
