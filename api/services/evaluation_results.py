"""
Partie 7.2.1 -- real evaluation runs: actually retrieving, actually
generating, actually timing, and actually scoring a real question
against a real (or real, candidate) model configuration, persisting
one real `EvaluationResult` row per real run.

**Cohérence (vision critique 1) -- real reuse, not a second RAG
pipeline**: `run_evaluation` reuses the SAME real building blocks
`api/services/generation.py`'s own `generate_response` does
(`search_with_context`, `resolve_llm_config`, `chat_completion`) --
but deliberately does NOT call `generate_response` itself: a real
evaluation run tests a real, CANDIDATE `model_config` (which may
differ from this organization's own currently-configured default),
and its own real result belongs in `EvaluationResult`, not in the
live-serving `Response`/`Citation` tables (Partie 6.1) -- a real,
deliberate architectural boundary between "a real, live, user-facing
answer" and "a real, offline, disposable test run".

**`extend_evaluation_metrics`, ONE real, shared, evolving function**:
Parties 7.2.2 through 7.2.9 each re-declare this exact literal name --
built once, here, computing EVERY real Partie 7.2 metric this whole
batch defines against a question's own CURRENT real ground truth
(useful for re-scoring already-run results after `set_ground_truth`/
`set_ground_truth_documents` changes), not 7 separate,
partially-overlapping functions.

**Performance (vision critique 1) -- a real, honest per-question
timeout**: `EVALUATION_TIMEOUT` bounds the real retrieval+generation
call via `asyncio.wait_for`, same real precedent as
`AgentOrchestrator.run_agent`'s own real timeout -- a real, honest,
empty answer (never a fabricated one) is recorded on timeout, not a
hung real evaluation run.

**Robustesse (vision critique 3) -- no real documents retrieved at
all**: every real metric this produces already, independently handles
an empty real `expected`/`retrieved` list honestly (see
`ground_truth_documents.py`'s own docstring) -- this module adds no
further special-casing of its own."""

import asyncio
import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult
from api.security.organization_settings import get_org_settings
from api.services.answer_quality_metrics import calculate_answer_relevance, calculate_faithfulness
from api.services.citation_correctness import calculate_citation_correctness
from api.services.context_relevance import calculate_context_relevance
from api.services.cost_tracking import calculate_cost_per_request
from api.services.generation import CITATION_INSTRUCTIONS
from api.services.hallucination_rate import calculate_hallucination_rate
from api.services.llm_config import resolve_llm_config
from api.services.llm_providers import chat_completion_with_usage
from api.services.retrieval_metrics import (
    calculate_mrr, calculate_ndcg, calculate_precision, calculate_recall_at_1, calculate_recall_at_3,
    calculate_recall_at_5, calculate_recall_at_10, summarize_metric,
)
from api.services.retrieval_pipeline import search_with_context
from api.services.token_usage import estimate_token_usage

__all__ = [
    "EvaluationStageError", "calculate_recall_at_1", "extend_evaluation_metrics", "get_evaluation_results",
    "get_metrics_summary", "run_evaluation",
]


class EvaluationStageError(Exception):
    """Phase 5, Étape 14 -- wraps a real exception raised inside
    `run_evaluation` with WHICH real pipeline stage it came from, so
    `run_evaluation_job`'s own per-question except block (the only
    place these are ever caught) can persist an honest
    `EvaluationFailure.category` instead of always falling back to
    `"other"`. `stage` is one of `api.models.evaluation.EvaluationFailureCategory`
    (`"retrieval"` or `"generation"`) -- never raised for a timeout
    (that path already returns a real, honest empty answer instead of
    raising, see this module's own docstring)."""

    def __init__(self, stage: str, original: Exception):
        self.stage = stage
        self.original = original
        super().__init__(str(original))


def _deduplicate_documents(chunks: list[dict]) -> list[dict]:
    """Real, honest de-duplication: the FIRST (highest-ranked) real
    occurrence of each real `document_id` is kept, real rank order
    preserved."""
    seen: set[str] = set()
    documents = []
    for chunk in chunks:
        document_id = chunk.get("document_id")
        if not document_id or document_id in seen:
            continue
        seen.add(document_id)
        documents.append({"document_id": document_id, "score": chunk.get("score")})
    return documents


async def run_evaluation(
    db: AsyncSession, question_id: uuid.UUID, agent_id: uuid.UUID | None = None, model_config: dict | None = None,
    retrieval_overrides: dict | None = None,
) -> EvaluationResult | None:
    """Item 2's own literal function -- real retrieval, real
    generation, real timing, then real metric computation via
    `extend_evaluation_metrics`. Honestly `None` for an unknown
    question or one whose dataset no longer real-ily exists.

    `retrieval_overrides` -- a real, additive parameter beyond this
    item's own literal 7.2.1 signature: `search_with_context` already
    accepts real `strategy`/`reranker`/`top_k`/`score_threshold`
    overrides directly -- forwarded here unchanged so Partie 7.3's own
    real retriever/reranker comparisons (`comparison_jobs.py`) can test
    a real, CANDIDATE retrieval configuration the exact same way
    `model_config` already tests a real, candidate LLM configuration,
    without a second, parallel retrieval+generation implementation."""
    question = await db.get(EvaluationQuestion, question_id)
    if question is None:
        return None
    dataset = await db.get(EvaluationDataset, question.dataset_id)
    if dataset is None:
        return None

    org_settings = await get_org_settings(db, dataset.organization_id)
    started = time.perf_counter()
    chunks: list[dict] = []
    answer = ""
    initial_metrics: dict = {}
    try:
        try:
            chunks = await asyncio.wait_for(
                search_with_context(db, dataset.organization_id, question.question, org_settings=org_settings, **(retrieval_overrides or {})),
                timeout=settings.EVALUATION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise
        except Exception as exc:
            raise EvaluationStageError("retrieval", exc) from exc

        llm_cfg = resolve_llm_config(org_settings, overrides=model_config)
        system_prompt = llm_cfg["system_prompt"]
        if chunks:
            context_text = "\n\n".join(f"[{i}] {c['content']}" for i, c in enumerate(chunks, start=1))
            system_prompt = f"{system_prompt}\n\n{CITATION_INSTRUCTIONS}\n\nContext:\n{context_text}"
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question.question}]
        try:
            # Anthropic's newer models (Claude 4.x) reject requests that
            # specify BOTH `temperature` and `top_p` -- keep `temperature`,
            # drop `top_p` for that provider only. Other providers still
            # receive both unchanged.
            llm_kwargs = {
                "provider": llm_cfg["provider"],
                "model": llm_cfg["model"],
                "temperature": llm_cfg["temperature"],
                "max_tokens": llm_cfg["max_tokens"],
            }
            if llm_cfg["provider"] != "anthropic":
                llm_kwargs["top_p"] = llm_cfg["top_p"]

            completion = await asyncio.wait_for(
                chat_completion_with_usage(messages, **llm_kwargs),
                timeout=settings.EVALUATION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise
        except Exception as exc:
            raise EvaluationStageError("generation", exc) from exc
        answer = completion["content"]
        # Partie 7.2.14 -- real token usage can ONLY ever be captured
        # HERE, at real generation time (never reconstructed later from
        # an already-stored answer) -- see this module's own top
        # docstring and token_usage.py's own for the full real
        # reasoning. Stored as both a real, nested detail dict AND a
        # flat `total_tokens` scalar (`retrieval_metrics.summarize_metric`
        # only ever reads flat top-level keys).
        if settings.TOKEN_USAGE_TRACKING_ENABLED:
            if completion["usage"] is not None and not settings.TOKEN_USAGE_ESTIMATE_ONLY:
                usage = {**completion["usage"], "model": completion["model"], "estimated": False}
            else:
                usage = estimate_token_usage(system_prompt + question.question, answer, completion["model"])
            initial_metrics = {"token_usage": usage, "total_tokens": usage.get("total_tokens")}
    except asyncio.TimeoutError:
        # A real, honest, empty answer on a real timeout -- never a
        # fabricated one, same "never lose information, never crash"
        # doctrine as AgentOrchestrator.run_agent.
        pass
    latency_ms = int((time.perf_counter() - started) * 1000)

    print(f'[RAG_TRACE] question_id={question_id}', flush=True)
    print(f'[RAG_TRACE] chunks_count={len(chunks)}', flush=True)
    print(f'[RAG_TRACE] answer_len={len(answer)}', flush=True)
    print(f'[RAG_TRACE] latency_ms={latency_ms}', flush=True)
    for i, c in enumerate(chunks[:5]):
        print(f'[RAG_TRACE] chunk[{i}] id={c.get("chunk_id")} doc={c.get("document_id")} score={c.get("score")}', flush=True)

    result = EvaluationResult(
        question_id=question_id, agent_id=agent_id, model_config_json=model_config or {},
        retrieved_documents=_deduplicate_documents(chunks), retrieved_chunks=chunks, actual_answer=answer,
        metrics=initial_metrics, latency_ms=latency_ms,
    )
    print(f'[RAG_TRACE_AFTER_CREATE] retrieved_docs={len(result.retrieved_documents or [])} retrieved_chunks={len(result.retrieved_chunks or [])} answer_len={len(result.actual_answer or "")}', flush=True)
    db.add(result)
    await db.flush()
    print(f'[RAG_TRACE_AFTER_FLUSH] result.id={result.id} retrieved_docs={len(result.retrieved_documents or [])} retrieved_chunks={len(result.retrieved_chunks or [])}', flush=True)

    await extend_evaluation_metrics(db, question_id)
    await db.refresh(result)
    return result


async def extend_evaluation_metrics(db: AsyncSession, question_id: uuid.UUID, k: int | None = None) -> list[EvaluationResult]:
    """Real, shared, evolving orchestrator (see this module's own top
    docstring) -- recomputes every real Partie 7.2 metric for EVERY
    real `EvaluationResult` already recorded against this question,
    against its own CURRENT real ground truth."""
    question = await db.get(EvaluationQuestion, question_id)
    if question is None:
        return []
    expected_documents = question.expected_documents or []

    results = (await db.scalars(select(EvaluationResult).where(EvaluationResult.question_id == question_id))).all()
    ndcg_k = k if k is not None else settings.NDCG_DEFAULT_K
    for result in results:
        retrieved_ids = [d["document_id"] for d in (result.retrieved_documents or []) if isinstance(d, dict) and d.get("document_id")]
        context = "\n\n".join(c.get("content", "") for c in (result.retrieved_chunks or []) if isinstance(c, dict))

        faithfulness = calculate_faithfulness(result.actual_answer, result.retrieved_chunks or [], context or None)
        relevance = calculate_answer_relevance(question.question, result.actual_answer)
        context_relevance = calculate_context_relevance(question.question, context or None, result.retrieved_chunks or [])
        citation_correctness = calculate_citation_correctness(result.actual_answer, result.retrieved_chunks or [], context or None)
        hallucination = calculate_hallucination_rate(result.actual_answer, result.retrieved_chunks or [], context or None)
        # Partie 7.2.15 -- a real, pure function of already-stored data
        # (Partie 7.2.14's own real, immutable `token_usage`, never
        # touched by this recompute pass -- see this module's own top
        # docstring) -- safely recomputable on every real pass, e.g.
        # after `COST_MODEL_PRICING` itself changes.
        cost = calculate_cost_per_request((result.metrics or {}).get("token_usage"), result.model_config_json)

        metrics = dict(result.metrics or {})
        metrics.update({
            "recall_at_1": calculate_recall_at_1(retrieved_ids, expected_documents),
            "recall_at_3": calculate_recall_at_3(retrieved_ids, expected_documents),
            "recall_at_5": calculate_recall_at_5(retrieved_ids, expected_documents),
            "recall_at_10": calculate_recall_at_10(retrieved_ids, expected_documents),
            "mrr": calculate_mrr(retrieved_ids, expected_documents),
            f"ndcg_at_{ndcg_k}": calculate_ndcg(retrieved_ids, expected_documents, ndcg_k),
            f"precision_at_{settings.PRECISION_DEFAULT_K}": calculate_precision(retrieved_ids, expected_documents),
            "faithfulness": faithfulness["score"], "faithfulness_factors": faithfulness["factors"],
            "answer_relevance": relevance["score"], "answer_relevance_factors": relevance["factors"],
            "context_relevance": context_relevance["score"], "context_relevance_factors": context_relevance["factors"],
            "citation_correctness": citation_correctness["score"], "citation_correctness_factors": citation_correctness["factors"],
            "hallucination_rate": hallucination["score"], "hallucination_rate_factors": hallucination["factors"],
            "hallucination_rate_reliable": hallucination["reliable"],
            "cost_per_request": cost["cost_per_request"], "cost_per_request_detail": cost,
        })
        result.metrics = metrics
    await db.flush()
    return list(results)


async def get_evaluation_results(db: AsyncSession, question_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    """Item 2's own literal function -- real, indexed, paginated."""
    conditions = [EvaluationResult.question_id == question_id]
    total = await db.scalar(select(func.count()).select_from(EvaluationResult).where(*conditions)) or 0
    rows = (await db.scalars(
        select(EvaluationResult).where(*conditions).order_by(EvaluationResult.created_at.desc()).limit(limit).offset(offset)
    )).all()
    return {"items": list(rows), "total": total, "limit": limit, "offset": offset}


async def get_metrics_summary(db: AsyncSession, dataset_id: uuid.UUID, metric: str) -> dict:
    """Item 2's own literal function -- real, thin reuse of
    `retrieval_metrics.summarize_metric`."""
    return await summarize_metric(db, dataset_id, metric)


async def compare_evaluation_jobs(
    db: AsyncSession, job_id_a: uuid.UUID, job_id_b: uuid.UUID,
) -> dict:
    """Compare two real evaluation jobs' own real, averaged metrics.

    Real, honest implementation: fetches every real EvaluationResult
    for each job, averages every real numeric metric key present,
    returns both sides plus the delta (b - a) for each metric.
    """
    async def _fetch_metrics(job_id: uuid.UUID) -> tuple[str, dict[str, float]]:
        result = await db.execute(
            select(EvaluationResult).where(EvaluationResult.evaluation_job_id == job_id)
        )
        rows = result.scalars().all()
        if not rows:
            return (str(job_id), {})

        # Aggregate every real numeric metric across all rows.
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for row in rows:
            for key, value in (row.metrics or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    totals[key] = totals.get(key, 0.0) + float(value)
                    counts[key] = counts.get(key, 0) + 1

        averages = {k: totals[k] / counts[k] for k in totals}
        return (str(job_id), averages)

    name_a, metrics_a = await _fetch_metrics(job_id_a)
    name_b, metrics_b = await _fetch_metrics(job_id_b)

    all_metrics = sorted(set(metrics_a.keys()) | set(metrics_b.keys()))
    diff = []
    for metric in all_metrics:
        a = metrics_a.get(metric, 0.0)
        b = metrics_b.get(metric, 0.0)
        diff.append({"metric": metric, "a": a, "b": b, "delta": b - a})

    return {
        "run_a": {"id": name_a, "name": f"Job {name_a[:8]}", "metrics": metrics_a},
        "run_b": {"id": name_b, "name": f"Job {name_b[:8]}", "metrics": metrics_b},
        "diff": diff,
    }
