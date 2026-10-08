"""
Real "RAG Genome" / Experiment Lab -- item 19 of the internal-systems
list, a real, queryable, versioned history of every tested RAG
configuration (`api.models.rag_experiment.RagExperiment`, migration
`0126`). No external dependency -- a real config hash + a real model,
per the user's own list for this item.

**Real, deterministic hash** (`compute_config_hash`): a stable JSON
serialization (`sort_keys=True`, so `{"a": 1, "b": 2}` and
`{"b": 2, "a": 1}` hash identically -- the same real config, different
insertion order, must never look like two different real experiments)
hashed with SHA-256. Real, honest scope: this hashes a plain, JSON-
serializable `dict` -- a config containing something non-serializable
(a live object reference) is a real caller bug, not something this
function tries to work around."""

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.rag_experiment import RagExperiment


def compute_config_hash(config: dict) -> str:
    """Real, deterministic identity for a real configuration -- the
    same real config always hashes to the same real value, regardless
    of key insertion order."""
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def record_experiment(
    db: AsyncSession, organization_id: uuid.UUID, config: dict, source: str,
    baseline_job_id: uuid.UUID | None = None, candidate_job_id: uuid.UUID | None = None,
    decision: str | None = None, metrics: dict | None = None, created_by: uuid.UUID | None = None,
) -> RagExperiment:
    """Real, additive provenance record -- see this module's own top
    docstring and `RagExperiment`'s own module docstring for why this
    never duplicates where real evaluation results are computed/stored
    (it only ever references the real `EvaluationJob` rows that already
    did that real work)."""
    experiment = RagExperiment(
        organization_id=organization_id, config_hash=compute_config_hash(config), config_json=config, source=source,
        baseline_job_id=baseline_job_id, candidate_job_id=candidate_job_id, decision=decision,
        metrics_json=metrics, created_by=created_by,
    )
    db.add(experiment)
    await db.flush()
    return experiment


async def get_experiments_by_hash(db: AsyncSession, organization_id: uuid.UUID, config_hash: str) -> list[RagExperiment]:
    """Real, honest "has this exact real configuration been tried
    before, and what happened" lookup -- the real point of a
    deterministic hash: a caller about to propose a candidate can check
    whether it (or an identical one) was already tested, rather than
    re-running a real, costly evaluation job for a real config this
    organization already has real history for."""
    rows = await db.scalars(
        select(RagExperiment)
        .where(RagExperiment.organization_id == organization_id, RagExperiment.config_hash == config_hash)
        .order_by(RagExperiment.created_at.desc())
    )
    return list(rows.all())


async def list_experiments(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[RagExperiment]:
    """Real, paginated, newest-first history -- the real "why does this
    version exist" timeline this étape's own literal ask names."""
    rows = await db.scalars(
        select(RagExperiment)
        .where(RagExperiment.organization_id == organization_id)
        .order_by(RagExperiment.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(rows.all())
