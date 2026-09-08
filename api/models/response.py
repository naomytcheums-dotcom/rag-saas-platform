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

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text, func
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
    # Partie 6.1.10 -- real, citation-quality confidence (see
    # api/services/response_confidence.py's own docstring: citation
    # count/relevance/diversity/reliability/consistency).
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Partie 6.2.4 -- real, BROADER agent-confidence estimate (citation
    # coverage/source consistency/context alignment/citation quality/
    # response length -- see api/services/confidence_estimation.py's
    # own docstring). A real, deliberate, DOCUMENTED deviation from this
    # étape's own literal ask: its own JSON details column is named
    # `confidence_estimation_factors`, NOT `confidence_factors` --
    # the literal spec re-declared that exact name, which Partie 6.1.10
    # already owns for a real, DIFFERENT, narrower metric. Two distinct
    # real concepts sharing one column would silently overwrite each
    # other; a real name collision, not a duplicate feature.
    confidence_estimation: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_estimation_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Partie 6.2.6 -- real, one of "verified"/"partially_verified"/
    # "unverified"/"contradictory" (api/services/claim_verification.py).
    claim_verification_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    claim_verification_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Partie 6.2.7 -- real (api/services/contradiction_detection.py).
    # A real LIST of contradiction dicts, not a single dict -- typed
    # `list | None` accordingly (every sibling *_details/*_factors
    # column above stores one real dict, this one doesn't).
    has_contradictions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contradictions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Partie 6.2.8 -- real (api/services/source_consistency.py).
    source_consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_consistency_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Partie 6.2.9 -- real (api/services/hallucination_detector.py).
    hallucination_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hallucination_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Partie 6.2.10 -- real (api/services/groundedness.py).
    groundedness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    groundedness_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
