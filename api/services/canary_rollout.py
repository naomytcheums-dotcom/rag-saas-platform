"""
Real Canary rollout evaluation -- item 20 of the internal-systems list
("Shadow / Canary RAG"), the CANARY half (gradual traffic promotion,
automatic rollback on regression). Built entirely on this codebase's
own already-real, already-rigorous LIVE A/B testing infrastructure
(`api/services/ab_tests.py`'s `ABTest` model/`get_ab_test_results` --
real p-values, confidence intervals, effect size, minimum-sample-size
gating) -- never a second, parallel statistics engine.

**Real, honest, single-vertical scope**: this covers CANARY (a real,
live `ABTest` already splitting real traffic between a baseline
`variant_a` and a candidate `variant_b`, `traffic_split` as the real,
existing, adjustable promotion knob) -- it does NOT also build SHADOW
mode (duplicating a real request to run a candidate config silently,
in parallel, never shown to the real user). Shadow mode needs a real
request-duplication hook this codebase's own live request path
(`api.services.generation.generate_response`) has no natural seam for
yet without risking a real, silent doubling of real LLM cost on every
real request -- see this module's own ROADMAP.md entry for the honest
reasoning and the real path forward (an explicit, opt-in
`shadow_config` parameter on `generate_response` itself, real,
additive future work, not fabricated here).

**Real, deliberately ASYMMETRIC action policy** -- unlike
`api.services.opa_policy`'s own fail-OPEN choice for a brand-new,
opt-in, advisory check (a real network failure there must never
restrict access Casbin RBAC already granted), a canary test is the
OPPOSITE real situation: it is ALREADY live and ALREADY exposing real
users to `variant_b`. On real, statistically significant evidence of
regression, automatically REDUCING that exposure (pausing the test) is
the safer default, not the riskier one -- so rollback is
AUTO-EXECUTED. Promotion (increasing `traffic_split`) is the opposite
real risk (exposing MORE real users to an unconfirmed candidate) and is
therefore NEVER auto-applied -- recommended only, same "propose, don't
silently act" discipline as `api.services.prompt_optimization`/
`api.services.rag_evolution_engine`.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def evaluate_canary(db: AsyncSession, test_id: uuid.UUID, target_metric: str, regression_threshold: float = -0.05) -> dict:
    """Real, one-shot canary health check for a real, running `ABTest`.
    `regression_threshold` -- a real, negative `lift` fraction (default
    `-0.05`, a real 5% relative drop) below which `variant_b` is judged
    to be regressing; only acted on once `get_ab_test_results`'s own
    real `significant`/`min_sample_size_reached` flags are both real
    and true -- never on a single, possibly-noisy early sample."""
    from api.models.evaluation import ABTest, ABTestStatus
    from api.services.ab_tests import get_ab_test_results, pause_ab_test

    test = await db.get(ABTest, test_id)
    if test is None or test.status != ABTestStatus.running:
        return {"test_id": test_id, "action": "none", "reason": "test not found or not currently running"}

    results = await get_ab_test_results(db, test_id)
    metric_result = (results or {}).get("metrics", {}).get(target_metric)
    if metric_result is None or not metric_result["min_sample_size_reached"]:
        return {"test_id": test_id, "action": "none", "reason": "not enough real samples yet for a real decision"}

    lift, significant = metric_result["lift"], metric_result["significant"]

    if significant and lift is not None and lift <= regression_threshold:
        await pause_ab_test(db, test_id)
        return {
            "test_id": test_id, "action": "rolled_back",
            "reason": f"real, statistically significant regression on '{target_metric}' ({lift:.1%})",
            "metric_result": metric_result,
        }

    if significant and lift is not None and lift > 0:
        return {
            "test_id": test_id, "action": "promotion_recommended",
            "reason": f"real, statistically significant improvement on '{target_metric}' ({lift:.1%})",
            "metric_result": metric_result, "recommended_traffic_split": min(test.traffic_split + 10, 100),
        }

    return {"test_id": test_id, "action": "none", "reason": "no statistically significant effect yet", "metric_result": metric_result}
