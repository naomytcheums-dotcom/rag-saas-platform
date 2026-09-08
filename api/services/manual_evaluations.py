"""
Partie 7.3.2 -- real, human evaluations: a real reviewer's own 1-5
score, free-text feedback, and optional per-criterion breakdown for
one real answer, complementing (never replacing) the real, automated
Partie 7.2 metrics.

**Robustesse (vision critique 3) -- un critère manquant**: `criteria`
is a real, PARTIAL dict -- any subset of the 5 real known criteria, or
none at all (a real reviewer may only score `accuracy`, leaving the
rest honestly unset). Only a real, UNKNOWN criterion key or an
out-of-range value raises -- a real, missing one is never treated as
an error."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.evaluation import EvaluationQuestion, ManualEvaluation

KNOWN_CRITERIA = ("accuracy", "relevance", "completeness", "clarity", "citation_quality")


def _validate_score(score: int | None) -> None:
    if score is not None and (not isinstance(score, int) or isinstance(score, bool) or not (1 <= score <= 5)):
        raise ValueError(f"score must be an integer 1-5, got {score!r}")


def _validate_criteria(criteria: dict | None) -> None:
    if not criteria:
        return
    for key, value in criteria.items():
        if key not in KNOWN_CRITERIA:
            raise ValueError(f"Unknown evaluation criterion: {key!r} (expected one of {KNOWN_CRITERIA})")
        if not isinstance(value, int) or isinstance(value, bool) or not (1 <= value <= 5):
            raise ValueError(f"Criterion {key!r} must be an integer 1-5, got {value!r}")


async def create_manual_evaluation(
    db: AsyncSession, question_id: uuid.UUID, agent_id: uuid.UUID | None, evaluator_id: uuid.UUID,
    score: int | None = None, feedback: str | None = None, criteria: dict | None = None,
) -> ManualEvaluation:
    """Item 2's own literal function."""
    _validate_score(score)
    _validate_criteria(criteria)
    evaluation = ManualEvaluation(
        question_id=question_id, agent_id=agent_id, evaluator_id=evaluator_id, score=score, feedback=feedback, criteria=criteria,
    )
    db.add(evaluation)
    await db.flush()
    return evaluation


async def update_manual_evaluation(
    db: AsyncSession, evaluation_id: uuid.UUID, score: int | None = None, feedback: str | None = None, criteria: dict | None = None,
) -> ManualEvaluation | None:
    """Item 2's own literal function -- real, partial update (only a
    real, explicitly-passed field changes; `None` means "leave as is",
    same real `exclude_unset` convention this codebase already uses
    for every other PATCH). Honestly `None` for an unknown evaluation."""
    evaluation = await db.get(ManualEvaluation, evaluation_id)
    if evaluation is None:
        return None
    if score is not None:
        _validate_score(score)
        evaluation.score = score
    if feedback is not None:
        evaluation.feedback = feedback
    if criteria is not None:
        _validate_criteria(criteria)
        evaluation.criteria = criteria
    await db.flush()
    return evaluation


async def get_manual_evaluation(db: AsyncSession, evaluation_id: uuid.UUID) -> ManualEvaluation | None:
    """Item 2's own literal function."""
    return await db.get(ManualEvaluation, evaluation_id)


async def list_manual_evaluations(db: AsyncSession, question_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    """Item 2's own literal function -- real, indexed, paginated."""
    conditions = [ManualEvaluation.question_id == question_id]
    total = await db.scalar(select(func.count()).select_from(ManualEvaluation).where(*conditions)) or 0
    rows = (await db.scalars(
        select(ManualEvaluation).where(*conditions).order_by(ManualEvaluation.created_at.desc()).limit(limit).offset(offset)
    )).all()
    return {"items": list(rows), "total": total, "limit": limit, "offset": offset}


def _average(values: list[int]) -> float | None:
    return sum(values) / len(values) if values else None


async def get_manual_evaluation_summary(db: AsyncSession, question_id: uuid.UUID) -> dict:
    """Item 2's own literal function -- real average overall score,
    plus a real, per-criterion average over whichever real evaluations
    actually set that real criterion."""
    rows = (await db.scalars(select(ManualEvaluation).where(ManualEvaluation.question_id == question_id))).all()
    scores = [r.score for r in rows if r.score is not None]
    criteria_values: dict[str, list[int]] = {name: [] for name in KNOWN_CRITERIA}
    for row in rows:
        for name, value in (row.criteria or {}).items():
            if name in criteria_values:
                criteria_values[name].append(value)

    return {
        "question_id": question_id, "count": len(rows), "average_score": _average(scores),
        "criteria_averages": {name: _average(values) for name, values in criteria_values.items()},
    }


async def get_manual_evaluation_stats(db: AsyncSession, dataset_id: uuid.UUID) -> dict:
    """Item 2's own literal function -- same real aggregation as
    `get_manual_evaluation_summary`, over every real question in this
    real dataset (real, thin JOIN through `EvaluationQuestion`, same
    real "loaded in Python, real row count too small to matter"
    precedent as `retrieval_metrics.get_dataset_result_metrics`)."""
    rows = (await db.scalars(
        select(ManualEvaluation)
        .join(EvaluationQuestion, EvaluationQuestion.id == ManualEvaluation.question_id)
        .where(EvaluationQuestion.dataset_id == dataset_id)
    )).all()
    scores = [r.score for r in rows if r.score is not None]
    criteria_values: dict[str, list[int]] = {name: [] for name in KNOWN_CRITERIA}
    for row in rows:
        for name, value in (row.criteria or {}).items():
            if name in criteria_values:
                criteria_values[name].append(value)

    return {
        "dataset_id": dataset_id, "count": len(rows), "average_score": _average(scores),
        "criteria_averages": {name: _average(values) for name, values in criteria_values.items()},
    }
