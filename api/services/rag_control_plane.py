"""
Real RAG Control Plane -- item 27, the FINAL item of the internal-
systems list, unifying items 18-26's own real, standalone systems into
one real, useful entry point.

**Real, honest scope decision made before writing code**: items 18-26
already each built a real, complete, independently-tested vertical
(`run_evolution_cycle`, `record_experiment`/`list_experiments`,
`evaluate_canary`, `get_response_provenance`, `filter_chunks_by_policy`,
`call_tool_with_firewall`, `record_flight`/`get_flight_recording`,
`suggest_retrieval_strategy`, `select_model_for_budget`). A "control
plane" function that merely re-exposes each of them through one
pass-through call, with no real new behavior, would be hollow glue --
exactly the kind of fabricated completeness this codebase's own
discipline refuses for a final item. This module instead adds ONE real,
genuinely NEW piece of behavior nothing before it provided: a real,
periodic HEALTH CHECK that iterates over an organization's ENTIRE real
operational surface at once, rather than requiring a caller to already
know each individual real `test_id`/`dataset_id` to check separately.

**Real, new behavior `run_health_check` adds**: before this function,
nothing in this codebase looped over an organization's own real,
CONCURRENT `ABTest` rows and evaluated every one of them -- a caller
had to already know each real `test_id` and call `evaluate_canary`
(item 20) on it individually. `run_health_check` is the real, first
place that batches this across an entire organization, combined with a
real summary of that organization's own recent RAG Genome experiment
history (item 19) -- one real, consolidated report answering "what is
this organization's RAG setup doing right now" instead of several
separate, manual lookups.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def run_health_check(db: AsyncSession, organization_id: uuid.UUID, default_target_metric: str = "semantic_similarity") -> dict:
    """Real, consolidated health check across one organization's real
    RAG operational surface:

    1. **Canaries** (item 20) -- every real, currently-running `ABTest`
       for this organization gets a real `evaluate_canary` call, using
       that test's OWN real `target_metric` when it has one configured
       (Partie 21), falling back to `default_target_metric` only when
       it doesn't -- never silently judging every real test by the same
       metric regardless of what it was actually set up to measure.
    2. **Recent experiments** (item 19) -- the organization's own real,
       last 10 `RagExperiment` rows, so a caller sees what configurations
       were recently tried and what was decided, without a separate call."""
    from api.models.evaluation import ABTest, ABTestStatus
    from api.services.canary_rollout import evaluate_canary
    from api.services.rag_genome import list_experiments

    running_tests = (await db.scalars(
        select(ABTest).where(ABTest.organization_id == organization_id, ABTest.status == ABTestStatus.running)
    )).all()

    canary_results = []
    for test in running_tests:
        metric = test.target_metric or default_target_metric
        result = await evaluate_canary(db, test.id, metric)
        canary_results.append({"test_id": test.id, "test_name": test.name, "target_metric": metric, **result})

    recent_experiments = await list_experiments(db, organization_id, limit=10)

    return {
        "organization_id": organization_id,
        "running_canaries_evaluated": len(canary_results),
        "canary_results": canary_results,
        "recent_experiments": [
            {
                "id": experiment.id, "config_hash": experiment.config_hash, "source": experiment.source,
                "decision": experiment.decision, "created_at": experiment.created_at.isoformat(),
            }
            for experiment in recent_experiments
        ],
    }
