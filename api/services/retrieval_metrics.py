"""
Parties 7.2.1/7.2.2/7.2.3/7.2.4/7.2.5/7.2.7 -- real, fixed-`k` retrieval
metrics, PLUS real, dataset-wide summaries.

**Cohérence -- real reuse, not 6 more reimplementations (décision
autonome)**: `calculate_recall_at_1`/`_3`/`_5`/`_10` are real, thin,
fixed-`k` wrappers around `ground_truth_documents.calculate_retrieval_recall`
(Partie 7.1.4) -- that function ALREADY computes real recall at ANY
real `k`; these 6 étapes' own literal asks for 4 SEPARATE
`calculate_recall_at_N` functions are the SAME real metric at 4 fixed
real `k` values, not 4 independently-computed ones. `calculate_precision`
similarly reuses `calculate_retrieval_precision`; `calculate_mrr`
reuses `calculate_retrieval_mrr` directly (it takes no real `k` at
all); `calculate_dcg`/`calculate_idcg`/`calculate_ndcg` are real,
direct re-exports of that same module's own Partie 7.2.6 additions.

**`extend_evaluation_metrics`, ONE real, evolving function, not 7
identically-named ones**: Parties 7.2.2 through 7.2.9 each re-declare
a literal `extend_evaluation_metrics(question_id)` -- the SAME real
name, meant to accumulate more real metrics into the SAME real
`EvaluationResult.metrics` JSON as each étape's own real work lands.
Built ONCE in `api/services/evaluation_results.py` (Partie 7.2.1's own
module, alongside `run_evaluation` -- a real `EvaluationResult` row is
what this function reads and rewrites, so it lives next to the real
code that creates one), which every one of these 6 étapes' own real
metric functions feeds into.

**Real, dataset-wide summaries, loaded in Python, not SQL-aggregated
(décision documentée)**: `EvaluationResult` has no real `dataset_id`
column of its own (only `question_id`) -- a real, per-metric-key SQL
`AVG` would need a real, cross-dialect JSON-path extraction
(`json_extract`/`->>`), a genuine portability risk between the SQLite
fast suite and real Postgres. Real evaluation results per real dataset
are realistically bounded (hundreds, not millions) -- the same
"grouped in Python, row count too small for a second query to be worth
it" precedent already established by `api/security/usage.py`'s own
`get_usage_summary`."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.evaluation import EvaluationQuestion, EvaluationResult
from api.services.ground_truth_documents import (
    calculate_dcg, calculate_idcg, calculate_retrieval_mrr, calculate_retrieval_ndcg, calculate_retrieval_precision,
    calculate_retrieval_recall,
)

__all__ = [
    "calculate_dcg", "calculate_idcg", "calculate_mrr", "calculate_ndcg", "calculate_precision", "calculate_recall_at_1",
    "calculate_recall_at_3", "calculate_recall_at_5", "calculate_recall_at_10", "get_dataset_result_metrics",
    "get_mrr_summary", "get_ndcg_summary", "get_precision_summary", "get_recall_summary", "summarize_metric",
]


def calculate_recall_at_1(retrieved_documents: list[str], expected_documents: list[dict]) -> float:
    """Item 2's own literal function (Partie 7.2.1) -- real, thin
    fixed-`k=1` reuse."""
    return calculate_retrieval_recall(retrieved_documents, expected_documents, k=1)


def calculate_recall_at_3(retrieved_documents: list[str], expected_documents: list[dict]) -> float:
    """Item 1's own literal function (Partie 7.2.2)."""
    return calculate_retrieval_recall(retrieved_documents, expected_documents, k=3)


def calculate_recall_at_5(retrieved_documents: list[str], expected_documents: list[dict]) -> float:
    """Item 1's own literal function (Partie 7.2.3)."""
    return calculate_retrieval_recall(retrieved_documents, expected_documents, k=5)


def calculate_recall_at_10(retrieved_documents: list[str], expected_documents: list[dict]) -> float:
    """Item 1's own literal function (Partie 7.2.4)."""
    return calculate_retrieval_recall(retrieved_documents, expected_documents, k=10)


def calculate_mrr(retrieved_documents: list[str], expected_documents: list[dict]) -> float:
    """Item 1's own literal function (Partie 7.2.5) -- real, direct
    re-export."""
    return calculate_retrieval_mrr(retrieved_documents, expected_documents)


def calculate_ndcg(retrieved_documents: list[str], expected_documents: list[dict], k: int | None = None) -> float:
    """Item 4's own literal function (Partie 7.2.6) -- real, direct
    re-export (see `ground_truth_documents.py`'s own docstring for the
    real exponential-gain upgrade)."""
    return calculate_retrieval_ndcg(retrieved_documents, expected_documents, k)


def calculate_precision(retrieved_documents: list[str], expected_documents: list[dict], k: int | None = None) -> float:
    """Item 1's own literal function (Partie 7.2.7) -- real, thin reuse,
    defaulting to `PRECISION_DEFAULT_K` (its own real, independently-
    configurable knob) rather than `GROUND_TRUTH_RETRIEVAL_K`."""
    k = k if k is not None else settings.PRECISION_DEFAULT_K
    return calculate_retrieval_precision(retrieved_documents, expected_documents, k)


async def get_dataset_result_metrics(db: AsyncSession, dataset_id: uuid.UUID) -> list[dict]:
    """Real, shared plumbing -- every real `EvaluationResult.metrics`
    dict for this real dataset (see this module's own top docstring
    for why this is loaded in Python, not SQL-aggregated). Public --
    `answer_quality_metrics.py`'s own Partie 7.2.8/7.2.9 summaries
    reuse this and `summarize_metric` below directly."""
    rows = (await db.scalars(
        select(EvaluationResult.metrics)
        .join(EvaluationQuestion, EvaluationQuestion.id == EvaluationResult.question_id)
        .where(EvaluationQuestion.dataset_id == dataset_id)
    )).all()
    return list(rows)


async def summarize_metric(db: AsyncSession, dataset_id: uuid.UUID, metric_key: str) -> dict:
    """Real, shared aggregation -- honestly `count=0`/`average=None`
    when no real evaluation result for this dataset has this real
    metric key at all."""
    values = [m[metric_key] for m in await get_dataset_result_metrics(db, dataset_id) if m.get(metric_key) is not None]
    if not values:
        return {"metric": metric_key, "count": 0, "average": None, "min": None, "max": None}
    return {"metric": metric_key, "count": len(values), "average": sum(values) / len(values), "min": min(values), "max": max(values)}


async def get_recall_summary(db: AsyncSession, dataset_id: uuid.UUID, k: int) -> dict:
    """Item 3's own literal function (Parties 7.2.2/7.2.3/7.2.4, same
    real name and signature in all 3 -- ONE real function, parameterized
    by `k`, not 3)."""
    return await summarize_metric(db, dataset_id, f"recall_at_{k}")


async def get_mrr_summary(db: AsyncSession, dataset_id: uuid.UUID) -> dict:
    """Item 3's own literal function (Partie 7.2.5)."""
    return await summarize_metric(db, dataset_id, "mrr")


async def get_ndcg_summary(db: AsyncSession, dataset_id: uuid.UUID, k: int | None = None) -> dict:
    """Item 5's own literal function (Partie 7.2.6)."""
    k = k if k is not None else settings.NDCG_DEFAULT_K
    return await summarize_metric(db, dataset_id, f"ndcg_at_{k}")


async def get_precision_summary(db: AsyncSession, dataset_id: uuid.UUID, k: int | None = None) -> dict:
    """Item 3's own literal function (Partie 7.2.7)."""
    k = k if k is not None else settings.PRECISION_DEFAULT_K
    return await summarize_metric(db, dataset_id, f"precision_at_{k}")
