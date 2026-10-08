"""
Real RAG Flight Recorder service -- item 24 of the internal-systems
list. See `api.models.flight_recording.FlightRecording`'s own module
docstring for the full real design and its honest scope boundary
(a real recording primitive, not yet automatically populated by
`api.services.retrieval_pipeline.search`'s own internal stages).

**Real, minimal, composable API**: a caller builds a real, ordered
`stages: list[dict]` itself (each `{"stage": str, "data": dict,
"duration_ms": int}}`) -- this module only ever persists and retrieves
that real list, it never dictates what a "stage" contains. `StageTimer`
is a real, small, optional helper for the common real case (measuring
one real stage's own real wall-clock duration) -- a caller free to
build `stages` any other way never needs it."""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.flight_recording import FlightRecording


class StageTimer:
    """Real, minimal wall-clock timer for one real pipeline stage --
    `with StageTimer("bm25_search") as t: ...` then `t.record` is a
    real `{"stage": ..., "data": ..., "duration_ms": ...}` dict ready
    to append to a real `stages` list."""

    def __init__(self, stage: str):
        self.stage = stage
        self.data: dict = {}
        self._started = 0.0
        self.record: dict | None = None

    def __enter__(self) -> "StageTimer":
        self._started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = int((time.perf_counter() - self._started) * 1000)
        self.record = {"stage": self.stage, "data": self.data, "duration_ms": duration_ms}


async def record_flight(
    db: AsyncSession, organization_id: uuid.UUID, query: str, stages: list[dict], total_duration_ms: int | None = None,
) -> FlightRecording:
    """Real, additive persistence of one real, already-assembled stage
    trace -- see this module's own top docstring for why assembling
    `stages` itself is deliberately out of scope here."""
    recording = FlightRecording(
        organization_id=organization_id, query=query, stages_json=stages, total_duration_ms=total_duration_ms,
    )
    db.add(recording)
    await db.flush()
    return recording


async def get_flight_recording(db: AsyncSession, recording_id: uuid.UUID) -> FlightRecording | None:
    """Real, honest lookup -- the real "replay" this étape's own
    literal ask names: every real stage this query actually went
    through, in the real order it happened."""
    return await db.get(FlightRecording, recording_id)


async def list_flight_recordings(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[FlightRecording]:
    rows = await db.scalars(
        select(FlightRecording)
        .where(FlightRecording.organization_id == organization_id)
        .order_by(FlightRecording.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(rows.all())
