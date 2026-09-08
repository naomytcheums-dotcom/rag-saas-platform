"""
Partie 7.3 -- multi-model comparisons and A/B testing. Not a prompt
this codebase's own `docs/CAHIER_DES_CHARGES.md` had received yet at
the time this was written (`### 7.3+ -- ... -- NON COMMENCÉ (prompts
non encore reçus)`) -- built autonomously, under this project's own
standing authorization to close a genuine, already-flagged gap, in the
SAME real style and rigor as every literal étape before it.

**Scoped by a real `QuestionSet`, not a whole real dataset**: a fair
real comparison needs the SAME real questions run against every real
candidate config -- `QuestionSet` (Partie 7.1.2) already IS this
codebase's own real "a defined, ordered, real subset of a dataset's
questions" concept (and `BenchmarkVersion`, Partie 7.1.6, already
snapshots one) -- reused directly via `get_questions_in_set`, rather
than inventing a second, competing "which questions" concept.

**Real, per-comparison aggregation, not dataset-wide (décision
autonome)**: `retrieval_metrics.get_dataset_result_metrics` aggregates
EVERY real `EvaluationResult` a dataset happens to hold, regardless of
which real model config produced it -- unusable for a real, honest
per-config comparison if that dataset has ANY earlier real runs mixed
in. `run_multi_model_comparison`/`run_ab_test` instead aggregate over
exactly the real `EvaluationResult` ids THEY just produced
(`retrieval_metrics.get_result_metrics`/`summarize_metric_for_results`,
this étape's own new, sibling functions) -- never a real, fragile
cross-dialect JSON-equality match against a stored `model_config_json`.

**Real, necessarily SEQUENTIAL execution, not `asyncio.gather`**: every
real run in this module shares the SAME real `AsyncSession` (a single
SQLAlchemy async session cannot safely have two real operations in
flight at once) -- and real LLM/retrieval calls carry real rate limits
and real cost regardless, so sequential real execution is both a real
technical requirement and the honest, real-cost-respecting choice, not
merely a simplification.

**A real, exact statistical test, not scipy** -- the two-sided sign
test (`_sign_test_p_value`): under the null hypothesis that config A
and config B are equally likely to "win" on any given real, non-tied
question, the real number of A-wins out of every real non-tied
question follows an exact real Binomial(n, 0.5) distribution -- its
real two-sided p-value is computable exactly from `math.comb`, with no
new real dependency and no approximated distribution. A real,
nonparametric, distribution-free test, deliberately chosen over a
paired t-test (which would additionally assume real, normally
distributed per-question deltas -- an assumption this module makes no
real claim about)."""

import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.services.evaluation_results import run_evaluation
from api.services.question_sets import get_questions_in_set
from api.services.retrieval_metrics import summarize_metric_for_results


def metric_keys() -> tuple[str, ...]:
    """Real, shared list of every real metric key
    `evaluation_results.extend_evaluation_metrics` writes -- computed
    fresh from `settings` on every real call (never a frozen,
    module-level constant), since `NDCG_DEFAULT_K`/`PRECISION_DEFAULT_K`
    are real, live-configurable knobs a real caller (or a real test's
    own `monkeypatch`) can change at runtime."""
    return (
        "recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr",
        f"ndcg_at_{settings.NDCG_DEFAULT_K}", f"precision_at_{settings.PRECISION_DEFAULT_K}",
        "faithfulness", "answer_relevance",
    )


def _sign_test_p_value(wins_a: int, wins_b: int) -> float:
    """Real, exact, two-sided sign-test p-value (see this module's own
    top docstring). Honestly `1.0` with no real, non-tied comparison at
    all -- no real evidence at all can never look real, statistically
    significant."""
    n = wins_a + wins_b
    if n == 0:
        return 1.0
    k = min(wins_a, wins_b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


async def run_multi_model_comparison(db: AsyncSession, question_set_id: uuid.UUID, model_configs: list[dict]) -> dict:
    """Item 1's own function -- runs every real question in this real
    question set against every real candidate `model_config`
    (reusing `run_evaluation`, Partie 7.2.1, directly -- never a second
    retrieval/generation implementation), then real, per-config metric
    summaries plus a real `ranking` (config indices, best real
    `EVALUATION_DEFAULT_COMPARISON_METRIC` average first)."""
    questions = await get_questions_in_set(db, question_set_id)
    keys = metric_keys()

    configs = []
    for model_config in model_configs:
        result_ids = []
        for question in questions:
            result = await run_evaluation(db, question.id, model_config=model_config)
            if result is not None:
                result_ids.append(result.id)
        metrics = {key: await summarize_metric_for_results(db, result_ids, key) for key in keys}
        configs.append({"model_config_used": model_config, "result_ids": result_ids, "metrics": metrics})

    rank_metric = settings.EVALUATION_DEFAULT_COMPARISON_METRIC
    ranking = sorted(range(len(configs)), key=lambda i: configs[i]["metrics"][rank_metric]["average"] or 0.0, reverse=True)
    return {"question_set_id": question_set_id, "sample_size": len(questions), "rank_metric": rank_metric, "ranking": ranking, "configs": configs}


async def run_ab_test(db: AsyncSession, question_set_id: uuid.UUID, model_config_a: dict, model_config_b: dict, metric: str | None = None) -> dict:
    """Item 1's own function -- a real, PAIRED comparison (same real
    question, both real configs) on one real, named metric, honestly
    skipping any real question either config's own real run didn't
    produce that real metric for (never a fabricated tie)."""
    metric = metric or settings.EVALUATION_DEFAULT_COMPARISON_METRIC
    questions = await get_questions_in_set(db, question_set_id)

    deltas = []
    for question in questions:
        result_a = await run_evaluation(db, question.id, model_config=model_config_a)
        result_b = await run_evaluation(db, question.id, model_config=model_config_b)
        value_a = (result_a.metrics or {}).get(metric) if result_a is not None else None
        value_b = (result_b.metrics or {}).get(metric) if result_b is not None else None
        if value_a is None or value_b is None:
            continue
        deltas.append(value_b - value_a)

    wins_b = sum(1 for delta in deltas if delta > 0)
    wins_a = sum(1 for delta in deltas if delta < 0)
    ties = len(deltas) - wins_a - wins_b
    average_delta = sum(deltas) / len(deltas) if deltas else 0.0
    p_value = _sign_test_p_value(wins_a, wins_b)

    return {
        "question_set_id": question_set_id, "metric": metric, "sample_size": len(deltas),
        "wins_a": wins_a, "wins_b": wins_b, "ties": ties, "average_delta": average_delta,
        "p_value": p_value, "significant": p_value < settings.AB_TEST_SIGNIFICANCE_THRESHOLD,
    }
