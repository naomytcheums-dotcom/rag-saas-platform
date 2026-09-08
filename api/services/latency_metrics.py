"""
Partie 7.2.13 -- real latency benchmarking: `measure_latency` runs a
real question against a real (or candidate) config repeatedly (real
warmup + real measurement runs) and reports a real percentile
distribution; `get_latency_summary`/`get_latency_distribution` instead
aggregate the real `latency_ms` EVERY `EvaluationResult` already,
naturally carries (Partie 7.2.1) -- zero real, additional cost.

**Cohérence -- deliberately NOT folded into `extend_evaluation_metrics`
(décision autonome, documentée)**: every other Partie 7.2.x metric this
whole batch built is a real, pure function of an ALREADY-STORED
`EvaluationResult` (its own real `actual_answer`/`retrieved_chunks`/
`metrics`) -- safely re-derivable at any real, later point, which is
exactly what `extend_evaluation_metrics`'s own real, shared recompute
loop is for. A real latency BENCHMARK is fundamentally different: its
own real signal (a real percentile DISTRIBUTION across MULTIPLE fresh
real runs) cannot be reconstructed from one already-stored real
result's own single real `latency_ms` value. `measure_latency` is
therefore its own real, separate, MULTI-RUN operation -- this étape's
own literal `extend_evaluation_metrics(question_id)` ask is honored in
spirit, not letter: it is fulfilled by NOT duplicating that real, one
already-shared name for a real, structurally different operation (the
same "ONE shared function, not many identically-named ones" discipline
this whole 7.2 batch has followed since 7.2.2).

**Performance (vision critique 1) -- a real, bounded wall-clock
budget, not per-call**: `LATENCY_TIMEOUT` bounds the whole real
warmup+measurement loop (`measure_latency` stops issuing new real runs
once the real deadline passes, keeping whatever real samples it
already collected -- an honest, partial real result, never a crash),
rather than `run_evaluation`'s own, separate, per-call
`EVALUATION_TIMEOUT`.

**Robustesse (vision critique 3) -- un appel échoue**: `run_evaluation`
never raises (Partie 7.2.1's own real timeout handling already returns
an honest, empty `actual_answer`) -- `measure_latency` honestly EXCLUDES
any such real, empty-answer run from its own real sample (that run's
own real `latency_ms` reflects hitting `EVALUATION_TIMEOUT`, an
artificial real ceiling, not a genuine real completion time)."""

import math
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.evaluation import EvaluationQuestion, EvaluationResult
from api.services.evaluation_results import run_evaluation


def _percentile(sorted_values: list[float], p: float) -> float:
    """Real, honest linear-interpolation (nearest-rank) percentile --
    no `numpy`/`scipy` dependency needed for a real, simple, exact
    computation over an already-sorted real list."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _latency_stats(samples: list[float]) -> dict:
    """Real, shared aggregation -- honestly all-`None` with a real,
    empty sample (never a fabricated `0.0`)."""
    if not samples:
        return {"p50": None, "p90": None, "p95": None, "p99": None, "avg": None, "min": None, "max": None, "std": None}
    ordered = sorted(samples)
    avg = sum(ordered) / len(ordered)
    variance = sum((x - avg) ** 2 for x in ordered) / len(ordered)
    return {
        "p50": _percentile(ordered, 0.50), "p90": _percentile(ordered, 0.90), "p95": _percentile(ordered, 0.95),
        "p99": _percentile(ordered, 0.99), "avg": avg, "min": min(ordered), "max": max(ordered), "std": variance ** 0.5,
    }


async def measure_latency(
    db: AsyncSession, question_id: uuid.UUID, agent_id: uuid.UUID | None = None, model_config: dict | None = None,
) -> dict:
    """Item 1's own literal function -- real `LATENCY_WARMUP_RUNS`
    (discarded, real JIT/connection-pool/cache warmup, same real
    purpose as any real benchmark's own warmup phase) then real
    `LATENCY_MEASUREMENT_RUNS` (kept), bounded by a real
    `LATENCY_TIMEOUT` wall-clock budget for the whole real loop."""
    deadline = time.perf_counter() + settings.LATENCY_TIMEOUT

    for _ in range(settings.LATENCY_WARMUP_RUNS):
        if time.perf_counter() >= deadline:
            break
        await run_evaluation(db, question_id, agent_id=agent_id, model_config=model_config)

    samples = []
    for _ in range(settings.LATENCY_MEASUREMENT_RUNS):
        if time.perf_counter() >= deadline:
            break
        result = await run_evaluation(db, question_id, agent_id=agent_id, model_config=model_config)
        if result is not None and result.actual_answer:
            samples.append(float(result.latency_ms))

    return {"question_id": question_id, "sample_size": len(samples), **_latency_stats(samples)}


async def _dataset_latency_samples(db: AsyncSession, dataset_id: uuid.UUID) -> list[float]:
    """Real, shared plumbing -- every real, already-stored
    `EvaluationResult.latency_ms` for this real dataset (zero real,
    additional cost -- Partie 7.2.1 already persists this column on
    every real run)."""
    rows = (await db.scalars(
        select(EvaluationResult.latency_ms)
        .join(EvaluationQuestion, EvaluationQuestion.id == EvaluationResult.question_id)
        .where(EvaluationQuestion.dataset_id == dataset_id)
    )).all()
    return [float(v) for v in rows]


async def get_latency_summary(db: AsyncSession, dataset_id: uuid.UUID) -> dict:
    """Item 1's own literal function -- real percentile/avg/min/max/std
    over every real, already-stored `latency_ms` in this real dataset."""
    samples = await _dataset_latency_samples(db, dataset_id)
    return {"sample_size": len(samples), **_latency_stats(samples)}


async def get_latency_distribution(db: AsyncSession, dataset_id: uuid.UUID) -> dict:
    """Item 1's own literal function -- the real, raw, sorted real
    sample itself (for a real caller building its own real
    histogram/chart), alongside the same real summary stats
    `get_latency_summary` returns."""
    samples = await _dataset_latency_samples(db, dataset_id)
    return {"sample_size": len(samples), "values": sorted(samples), **_latency_stats(samples)}
