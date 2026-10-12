"""One end-to-end view of a single answer: the question, retrieval, generation, checks, citations and the agent's steps (spec 13.5.12).

Until now these facts lived in four places (the response row, the flight recording, the agent run and its step traces, the citations). This joins
them in memory, ordered in time, so an operator can read "what happened to this question" in one call. It only reads: nothing is written.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent_run import AgentRunRecord
from api.models.agent_trace import AgentTrace
from api.models.citation import Citation
from api.models.flight_recording import FlightRecording
from api.models.response import Response


def _seconds(delta) -> float | None:
    return None if delta is None else round(delta.total_seconds(), 3)


async def build_request_trace(db: AsyncSession, response: Response) -> dict[str, Any]:
    """Assemble the trace of `response`. The caller has already checked that the user may read it."""
    stages: list[dict[str, Any]] = []

    recording = await db.get(FlightRecording, response.flight_recording_id) if response.flight_recording_id else None
    if recording is not None and recording.organization_id == response.organization_id:
        for index, stage in enumerate(recording.stages_json or []):
            stages.append({"source": "flight_recorder", "order": index, "detail": stage})

    run = await db.scalar(select(AgentRunRecord).where(AgentRunRecord.response_id == response.id, AgentRunRecord.organization_id == response.organization_id))
    steps: list[AgentTrace] = []
    if run is not None:
        steps = list((await db.scalars(select(AgentTrace).where(AgentTrace.agent_run_id == run.id).order_by(AgentTrace.step_number))).all())
        for step in steps:
            stages.append({
                "source": "agent", "order": step.step_number,
                "detail": {"type": step.step_type, "description": step.description, "status": step.status, "duration_ms": step.duration_ms, "error": step.error},
            })

    citations = list((await db.scalars(select(Citation).where(Citation.response_id == response.id).order_by(Citation.citation_number))).all())

    failed_steps = [s.step_number for s in steps if s.status not in ("completed", "started") or s.error]
    return {
        "response_id": response.id,
        "organization_id": response.organization_id,
        "question": response.query,
        "answer_excerpt": response.answer[:500],
        "created_at": response.created_at,
        "retrieval": {"strategy": response.retrieval_strategy, "embedding_model": response.embedding_model, "citations_used": len(citations)},
        "generation": {"provider": response.llm_provider, "model": response.llm_model},
        "checks": {
            "confidence": response.confidence_score, "groundedness": response.groundedness_score, "faithfulness": response.faithfulness_score,
            "hallucination": response.hallucination_score, "has_contradictions": response.has_contradictions, "has_unsupported_claims": response.has_unsupported_claims,
        },
        "agent_run": None if run is None else {
            "id": run.id, "agent_id": run.agent_id, "status": run.status, "error": run.error,
            "duration_seconds": _seconds(run.completed_at - run.started_at) if run.completed_at and run.started_at else None,
        },
        "recorded_stages": len(recording.stages_json or []) if recording is not None else 0,
        "total_duration_ms": recording.total_duration_ms if recording is not None else None,
        "citations": [
            {"number": c.citation_number, "document_id": c.document_id, "document_name": c.document_name, "page": c.source_page, "relevance": c.relevance_score}
            for c in citations
        ],
        "failed_agent_steps": failed_steps,
        "timeline": stages,
    }

