"""
Real RAG Evolution Engine -- item 18 of the internal-systems list,
built on real, already-existing infrastructure: item 11's DSPy prompt
optimization (`api/services/prompt_optimization.py`) + the Eval Lab's
own real, already-tested benchmark/comparison machinery
(`api/services/evaluation_jobs.py`'s `create_evaluation_job`/
`run_evaluation_job`, `compare_evaluation_jobs`). Turns the honest gap
this project's own `AGENTS.md` names ("ChangeLab" acting on "je pense
que" rather than measured evidence) into a real, measured loop: a real
baseline run, a real DSPy-proposed candidate, a real second run of the
SAME dataset with that candidate, a real, existing metric comparison --
"j'ai testé 2 candidats, B gagne de X à Y" instead of an assertion.

**Real, honest, single-dimension scope**: the ONE real candidate this
engine can propose today is a DSPy-optimized `system_prompt` (item 11's
own real mechanism) -- it does NOT also search over
`retrieval_strategy`/`top_k`/chunking parameters, even though
`run_evaluation`'s own real `retrieval_overrides` parameter
(`api/services/evaluation_results.py`) would technically support
testing those too. Claiming a real, multi-dimensional optimization loop
without a real second candidate-generation mechanism to drive it would
be exactly the kind of fabricated completeness this codebase's own
discipline refuses -- see this module's own ROADMAP.md entry for the
real, honest next step (a retrieval-config candidate generator,
symmetric to `optimize_system_prompt`).

**Never auto-applies a winning candidate** -- same "propose, never
silently change existing behavior" discipline as
`optimize_system_prompt` itself: this function returns a real,
evidence-backed RECOMMENDATION (which real job won, by how much, on
which real metric); applying it to `organization_settings.system_prompt`
remains a separate, explicit, human-reviewed call to the already-real
`update_org_settings`.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def run_evolution_cycle(
    db: AsyncSession, dataset_id: uuid.UUID, llm_provider: str, llm_model: str | None = None,
    target_metric: str = "semantic_similarity",
) -> dict:
    """Real, 6-phase evolution cycle over one real evaluation dataset:

    1. **Observe** -- a real, fresh baseline `EvaluationJob` (no
       overrides -- this organization's own real, currently-configured
       `system_prompt`).
    2. **Diagnose/Propose** -- `optimize_system_prompt` (item 11) mines
       the SAME dataset's own real ground truth for a real candidate
       `system_prompt`. Real, honest early exit: fewer than
       `MIN_GROUND_TRUTH_EXAMPLES` real ground-truth answers, or a
       candidate that exceeds the real runtime length limit, ends the
       cycle here -- never a fabricated experiment run on a candidate
       this codebase already knows can't be used.
    3. **Experiment** -- a real, SECOND `EvaluationJob`, over the exact
       same real dataset/questions, with `model_config={"system_prompt":
       candidate}` (the same real override seam `run_evaluation`
       already exposes for Partie 7.3's own comparison jobs).
    4. **Measure** -- the real, already-existing `compare_evaluation_jobs`
       (real averaged metrics, real per-metric delta).
    5. **Recommend** -- `target_metric`'s own real delta decides
       `"candidate_recommended"` vs `"baseline_kept"` -- NEVER
       auto-applied (see this module's own top docstring)."""
    from api.services.evaluation_jobs import compare_evaluation_jobs, create_evaluation_job, run_evaluation_job
    from api.services.prompt_optimization import NotEnoughGroundTruthError, optimize_system_prompt

    baseline_job = await create_evaluation_job(db, dataset_id)
    await db.commit()
    baseline_job = await run_evaluation_job(db, baseline_job.id)

    try:
        optimization = await optimize_system_prompt(db, dataset_id, llm_provider, llm_model)
    except NotEnoughGroundTruthError as exc:
        return {
            "baseline_job_id": baseline_job.id, "candidate_job_id": None, "decision": "insufficient_ground_truth",
            "reason": str(exc),
        }

    if optimization["exceeds_runtime_limit"]:
        return {
            "baseline_job_id": baseline_job.id, "candidate_job_id": None, "decision": "candidate_rejected",
            "reason": (
                f"DSPy-optimized prompt ({len(optimization['system_prompt'])} chars) exceeds the real runtime "
                f"limit of {optimization['runtime_limit']} chars"
            ),
        }

    candidate_job = await create_evaluation_job(db, dataset_id, model_config={"system_prompt": optimization["system_prompt"]})
    await db.commit()
    candidate_job = await run_evaluation_job(db, candidate_job.id)

    comparison = await compare_evaluation_jobs(db, baseline_job.id, candidate_job.id)
    target_diff = next((d for d in comparison["diff"] if d["metric"] == target_metric), None)
    candidate_wins = target_diff is not None and target_diff["delta"] > 0
    decision = "candidate_recommended" if candidate_wins else "baseline_kept"

    # Real RAG Genome recording (item 19, api/services/rag_genome.py) --
    # only recorded here, once a FULL real cycle actually produced a
    # real comparison: an early exit above (insufficient ground truth,
    # a rejected candidate) has no real candidate/decision/metrics yet
    # worth a permanent history row for. `organization_id` resolved
    # from the real dataset (same real "fetch it from the entity being
    # evaluated" pattern as `run_evaluation` itself).
    from api.models.evaluation import EvaluationDataset
    from api.services.rag_genome import record_experiment

    dataset = await db.get(EvaluationDataset, dataset_id)
    await record_experiment(
        db, dataset.organization_id, config={}, source="rag_evolution_engine",
        baseline_job_id=baseline_job.id, decision=decision, metrics=comparison,
    )
    await record_experiment(
        db, dataset.organization_id, config={"system_prompt": optimization["system_prompt"]}, source="rag_evolution_engine",
        candidate_job_id=candidate_job.id, decision=decision, metrics=comparison,
    )
    await db.commit()

    return {
        "baseline_job_id": baseline_job.id, "candidate_job_id": candidate_job.id, "comparison": comparison,
        "target_metric": target_metric, "target_metric_delta": target_diff["delta"] if target_diff else None,
        "decision": decision, "candidate_system_prompt": optimization["system_prompt"] if candidate_wins else None,
    }


# ---------------------------------------------------------------------------
# Hardening Mission (§12, Evolution Engine) -- retrieval-configuration
# candidates: the "real, honest next step" the module docstring above names.
# ---------------------------------------------------------------------------

# Metrics where a HIGHER value is WORSE (a regression is a positive delta).
_LOWER_IS_BETTER = {"hallucination_rate"}
_GUARD_METRICS = ("recall_at_5", "mrr", "semantic_similarity", "hallucination_rate")


def default_retrieval_candidates(org_settings: dict) -> list[dict]:
    """Deterministic, data-independent candidate generator, derived from the
    organization's CURRENT effective settings so every candidate really
    differs from the baseline: a wider top_k, cross-encoder reranking, both
    together, and MMR diversification. Each is validated against the same
    `validate_retrieval_config` an external caller goes through."""
    from api.config import settings
    from api.services.agent_knowledge_base import validate_retrieval_config

    current_top_k = int(org_settings.get("top_k") or 5)
    wider = min(current_top_k * 2, settings.TOP_K_MAX)
    raw = [{"top_k": wider}, {"strategy": "hybrid_reranked"}, {"strategy": "hybrid_reranked", "top_k": wider}, {"mmr": True}]
    candidates, seen = [], set()
    for config in raw:
        if config.get("top_k") == current_top_k and len(config) == 1:
            continue  # identical to the baseline -- not a candidate
        validated = validate_retrieval_config(config)
        key = tuple(sorted(validated.items()))
        if key not in seen:
            seen.add(key)
            candidates.append(validated)
    return candidates


def judge_candidate(comparison: dict, target_metric: str, min_improvement: float, max_regression: float, extra_guard_metrics: tuple[str, ...] = ()) -> dict:
    """Pure decision rule, unit-testable without any job: a candidate is
    ACCEPTED only if (1) the target metric improved by at least
    `min_improvement` (a tiny positive delta is noise, not a win) AND
    (2) NO guard metric got materially worse (`max_regression`, direction-
    aware: for `hallucination_rate` an INCREASE is the regression). A change
    that improves one number by degrading another is rejected with the
    precise reason, never recommended."""
    diff = {d["metric"]: d for d in comparison.get("diff", [])}
    reasons: list[str] = []

    target = diff.get(target_metric)
    if target is None:
        return {"accepted": False, "target_delta": None, "reasons": [f"target metric {target_metric!r} was not computed for both runs"]}
    if target["delta"] < min_improvement:
        reasons.append(f"{target_metric} improved by {target['delta']:+.4f}, below the required minimum of {min_improvement:+.4f}")

    guards = [m for m in dict.fromkeys((*_GUARD_METRICS, *extra_guard_metrics)) if m != target_metric and m in diff]
    guards += [m for m in diff if m.startswith("ndcg_at_") and m != target_metric and m not in guards]
    for metric in guards:
        delta = diff[metric]["delta"]
        worsened = delta > max_regression if metric in _LOWER_IS_BETTER else delta < -max_regression
        if worsened:
            reasons.append(f"{metric} regressed by {delta:+.4f} (allowed: {max_regression:.4f})")
    return {"accepted": not reasons, "target_delta": target["delta"], "reasons": reasons}


async def run_retrieval_evolution_cycle(
    db: AsyncSession, dataset_id: uuid.UUID, candidates: list[dict] | None = None, target_metric: str = "recall_at_5",
    min_improvement: float = 0.02, max_regression: float = 0.05,
) -> dict:
    """Real multi-candidate retrieval-configuration search over ONE
    evaluation dataset: a baseline job (current effective configuration),
    then one job per candidate over the SAME questions with that candidate
    applied for real (`run_evaluation(retrieval_config=...)`), each compared
    to the baseline with `compare_evaluation_jobs` and judged by
    `judge_candidate` (minimum improvement + no-regression guard). Every
    tested candidate is reported with its measured delta and the reasons it
    was rejected -- "I tested N, B wins by X" with the evidence for the
    losers too. The best ACCEPTED candidate (largest target delta) is
    RECOMMENDED, never applied: applying is the separate, explicit
    `apply_retrieval_recommendation`, which returns the previous config so
    it can be rolled back."""
    from api.models.evaluation import EvaluationDataset
    from api.security.organization_settings import get_org_settings
    from api.services.agent_knowledge_base import validate_retrieval_config
    from api.services.evaluation_jobs import compare_evaluation_jobs, create_evaluation_job, run_evaluation_job
    from api.services.rag_genome import record_experiment

    dataset = await db.get(EvaluationDataset, dataset_id)
    if dataset is None:
        raise ValueError(f"Dataset not found: {dataset_id}")
    org_settings = await get_org_settings(db, dataset.organization_id)
    candidate_configs = [validate_retrieval_config(c) for c in candidates] if candidates else default_retrieval_candidates(org_settings)

    baseline_job = await create_evaluation_job(db, dataset_id)
    await db.commit()
    baseline_job = await run_evaluation_job(db, baseline_job.id)

    tested: list[dict] = []
    for config in candidate_configs:
        job = await create_evaluation_job(db, dataset_id, model_config={"retrieval_config": config})
        await db.commit()
        job = await run_evaluation_job(db, job.id)
        comparison = await compare_evaluation_jobs(db, baseline_job.id, job.id)
        verdict = judge_candidate(comparison, target_metric, min_improvement, max_regression)
        tested.append({"config": config, "job_id": job.id, "comparison": comparison, **verdict})

    accepted = [t for t in tested if t["accepted"]]
    best = max(accepted, key=lambda t: t["target_delta"]) if accepted else None
    decision = "candidate_recommended" if best else "baseline_kept"

    await record_experiment(db, dataset.organization_id, config={}, source="rag_evolution_engine.retrieval", baseline_job_id=baseline_job.id, decision=decision, metrics={"target_metric": target_metric})
    for t in tested:
        await record_experiment(
            db, dataset.organization_id, config=t["config"], source="rag_evolution_engine.retrieval", candidate_job_id=t["job_id"],
            decision="candidate_recommended" if best is t else ("candidate_rejected" if not t["accepted"] else "candidate_not_best"), metrics=t["comparison"],
        )
    await db.commit()

    return {
        "baseline_job_id": baseline_job.id, "target_metric": target_metric, "min_improvement": min_improvement, "max_regression": max_regression,
        "decision": decision, "recommended_config": best["config"] if best else None, "candidates": tested,
        "corpus_constrained": bool(((baseline_job.results or {}).get("corpus_constrained"))),
    }


async def apply_retrieval_recommendation(db: AsyncSession, organization_id: uuid.UUID, agent_id: uuid.UUID, config: dict, replace: bool = False) -> dict:
    """The explicit, human-triggered APPLY step (never called by the cycle
    above): writes a validated retrieval config to the agent's
    `knowledge_base_config` (merged, or replacing it with `replace=True`)
    and returns `{"previous", "current"}`. Rolling back is the same call
    with `config=previous, replace=True`. The agent must belong to
    `organization_id` (404-style `ValueError` otherwise)."""
    from sqlalchemy import select

    from api.models.agent import Agent
    from api.services.agent_knowledge_base import validate_retrieval_config

    validated = validate_retrieval_config(config) if config else {}
    agent = await db.scalar(select(Agent).where(Agent.id == agent_id, Agent.organization_id == organization_id, Agent.deleted_at.is_(None)))
    if agent is None:
        raise ValueError(f"Agent not found: {agent_id}")
    previous = dict(agent.knowledge_base_config or {})
    agent.knowledge_base_config = validated if replace else {**previous, **validated}
    await db.flush()
    return {"previous": previous, "current": dict(agent.knowledge_base_config)}


async def run_multi_dataset_retrieval_evolution(
    db: AsyncSession, dataset_ids: list[uuid.UUID], candidates: list[dict] | None = None, target_metric: str = "recall_at_5",
    min_improvement: float = 0.02, max_regression: float = 0.05,
) -> dict:
    """Hardening Mission (§12) -- the same candidate set evaluated on SEVERAL datasets. A setting that wins on one
    question set can simply be overfitted to it; here a candidate is recommended only if it is ACCEPTED on EVERY
    dataset (minimum gain AND no guard-metric regression on each), and candidates are ranked by their MEAN target
    gain across datasets. All datasets must belong to one organization. With a single dataset this is exactly
    `run_retrieval_evolution_cycle`."""
    from api.models.evaluation import EvaluationDataset
    from api.security.organization_settings import get_org_settings

    unique_ids = list(dict.fromkeys(dataset_ids))
    if not unique_ids:
        raise ValueError("at least one dataset is required")
    datasets = [await db.get(EvaluationDataset, dataset_id) for dataset_id in unique_ids]
    if any(d is None for d in datasets):
        raise ValueError("Dataset not found")
    if len({d.organization_id for d in datasets}) != 1:
        raise ValueError("all datasets must belong to the same organization")

    if candidates is None:
        candidates = default_retrieval_candidates(await get_org_settings(db, datasets[0].organization_id))

    cycles = [
        await run_retrieval_evolution_cycle(db, dataset_id, candidates, target_metric, min_improvement, max_regression)
        for dataset_id in unique_ids
    ]
    aggregated = []
    for index, config in enumerate(cycles[0]["candidates"]):
        per_dataset = [cycle["candidates"][index] for cycle in cycles]
        deltas = [c["target_delta"] for c in per_dataset]
        measured = [d for d in deltas if d is not None]
        reasons = [f"dataset {n + 1}: {reason}" for n, c in enumerate(per_dataset) for reason in c["reasons"]]
        aggregated.append({
            "config": config["config"], "per_dataset_delta": deltas, "mean_target_delta": sum(measured) / len(measured) if measured else None,
            "accepted_on_all": all(c["accepted"] for c in per_dataset), "reasons": reasons,
        })
    winners = [c for c in aggregated if c["accepted_on_all"]]
    best = max(winners, key=lambda c: c["mean_target_delta"]) if winners else None
    return {
        "datasets_evaluated": len(unique_ids), "target_metric": target_metric, "min_improvement": min_improvement, "max_regression": max_regression,
        "decision": "candidate_recommended" if best else "baseline_kept", "recommended_config": best["config"] if best else None,
        "candidates": aggregated, "per_dataset": [
            {"dataset_id": dataset_id, "baseline_job_id": cycle["baseline_job_id"], "decision": cycle["decision"], "corpus_constrained": cycle["corpus_constrained"]}
            for dataset_id, cycle in zip(unique_ids, cycles)
        ],
    }
