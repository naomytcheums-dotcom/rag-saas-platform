"""
Partie 6.1.1 -- the real, persisted `Response` entity this codebase
has been honestly missing: `api/security/organization_settings.py`'s
own module docstring already documented the gap by name -- "a real,
live, multi-tenant HTTP endpoint that actually ANSWERS a question
(retrieval + generation combined, citing sources, honoring
citation_required/language) is still real, substantial, separate work
belonging to Partie 9 (or whichever later étape actually asks for
it)". This étape is that later étape: `api/services/generation.py`'s
own real `generate_response` is the first real, live caller.

**Real, multi-tenant equivalent of the legacy, single-tenant
`src/generation.py`** -- that script builds an LLM prompt with inline
`[1]`/`[2]` bracket citations baked into the raw generated text, with
nothing structured or queryable behind them. `Response`/`Citation`
(Partie 6.1.1) are the real, structured, per-organization equivalent:
a real row per real generated answer, with real, separate `Citation`
rows a real caller can list/filter/format independently of the
answer's own raw text."""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Partie 6.1.10 -- real, inert until that étape's own
    # calculate_confidence_score/calculate_confidence_factors.
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
