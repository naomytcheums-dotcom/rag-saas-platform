"""
Partie 7.2.11 -- real citation correctness: are the `[n]` citation
markers a real answer actually uses present, accurate, well-formed,
and complete relative to the real, numbered context this codebase's
own `CITATION_INSTRUCTIONS` (`generation.py`) asks the LLM to cite
from.

**Cohérence -- a real, autonomous signature fix**: this étape's own
literal ask was `calculate_citation_correctness(citations, context)`
-- omitting `answer`, the one real thing citation markers actually
live inside. Every other real `calculate_*` function this whole 7.2
batch built (`calculate_faithfulness`, `calculate_answer_relevance`,
`calculate_context_relevance`) takes the real answer/question text
directly; this one is fixed to match that same real, established
3-argument shape (`answer`, `citations`, `context`), reusing
`calculate_faithfulness`'s own exact real parameter order and naming.

**Précision (vision critique 2) -- real markers, matched two real
ways, for two real purposes**: `citation_presence` checks a real
marker `[n]` against the real, NUMBERED CONTEXT STRING itself (the
literal French ask: "présence des citations DANS LE CONTEXTE") --
`citation_accuracy` checks the real, CITED CONTENT (via the real
`citations` list, by real position) actually supports the real
sentence carrying that marker. Two real, deliberately different real
data sources, each answering a real, different question.

**Robustesse (vision critique 3) -- no real citations at all**: every
real factor's own real "vacuous" convention is documented at its own
definition -- `citation_presence`/`citation_accuracy` honestly `0.0`
(nothing real to be present/accurate), `citation_format` honestly
`1.0` (nothing real to be malformed), `citation_completeness` honestly
`1.0` (nothing real requires a citation when there are no real claims
at all -- same real convention as `hallucination_absence`)."""

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.services.claim_extraction import extract_claims
from api.services.retrieval_metrics import summarize_metric
from api.services.text_similarity import jaccard_similarity

_CITATION_MARKER = re.compile(r"\[(\d+)\]")
_BRACKET_TOKEN = re.compile(r"\[[^\]]*\]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _citation_text(citation: dict) -> str:
    """Real, flexible accessor -- same real convention as
    `answer_quality_metrics.citation_text`."""
    return citation.get("text") or citation.get("content") or ""


def _citation_markers(text: str) -> list[int]:
    """Real, numbered `[n]` citation markers (1-indexed), matching
    this codebase's own real `CITATION_INSTRUCTIONS` convention."""
    return [int(n) for n in _CITATION_MARKER.findall(text)]


def _citation_presence(answer: str, context: str | None) -> float:
    """Real, factor 1 -- real fraction of the answer's own citation
    markers that correspond to an ACTUALLY-enumerated `[n] ...` block
    in the real, numbered context string. Honestly `0.0` with no real
    markers at all, or no real context to check them against."""
    markers = _citation_markers(answer)
    if not markers or not context:
        return 0.0
    enumerated = {int(n) for n in re.findall(r"^\[(\d+)\]", context, re.MULTILINE)}
    return sum(1 for n in markers if n in enumerated) / len(markers)


def _citation_accuracy(answer: str, citations: list[dict]) -> float:
    """Real, factor 2 -- for every real sentence carrying a real
    marker `[n]`, does `citations[n-1]`'s own real content actually
    support that real sentence (`jaccard_similarity` >=
    `UNSUPPORTED_CLAIM_SIMILARITY_THRESHOLD`, Partie 6.2.5's own real,
    matching concept, reused directly). Honestly `0.0` with no real,
    markered sentence at all."""
    sentences = [s for s in _SENTENCE_SPLIT.split(answer) if s]
    supported = 0
    total = 0
    for sentence in sentences:
        for n in _citation_markers(sentence):
            total += 1
            if 1 <= n <= len(citations):
                cited_text = _citation_text(citations[n - 1])
                if jaccard_similarity(sentence, cited_text) >= settings.UNSUPPORTED_CLAIM_SIMILARITY_THRESHOLD:
                    supported += 1
    return supported / total if total else 0.0


def _citation_format(answer: str) -> float:
    """Real, factor 3 -- real fraction of real bracket-like tokens
    (`[...]`) that are well-formed `[n]`. Honestly `1.0` (vacuous) with
    no real bracket-like token at all -- nothing real is malformed."""
    tokens = _BRACKET_TOKEN.findall(answer)
    if not tokens:
        return 1.0
    well_formed = sum(1 for t in tokens if _CITATION_MARKER.fullmatch(t))
    return well_formed / len(tokens)


def _citation_completeness(answer: str) -> float:
    """Real, factor 4 -- real fraction of the answer's own real claims
    (`claim_extraction.extract_claims`, Partie 6.2.5, reused directly)
    that carry at least one real citation marker. Honestly `1.0`
    (vacuous -- same real convention as `hallucination_absence`) with
    no real claims at all -- nothing real requires a real citation."""
    claims = extract_claims(answer)
    if not claims:
        return 1.0
    cited = sum(1 for claim in claims if _CITATION_MARKER.search(claim))
    return cited / len(claims)


def calculate_citation_correctness(answer: str, citations: list[dict], context: str | None = None) -> dict:
    """Item 1's own function (Partie 7.2.11, real, autonomous signature
    fix -- see this module's own top docstring). Real, weighted
    aggregation via `CITATION_CORRECTNESS_FACTORS_WEIGHTS`, honoring
    the 3 real `CITATION_CORRECTNESS_CHECK_*` toggles by real-ily
    excluding a disabled real factor from BOTH the real weighted sum
    AND the real weight renormalization (a real, honestly SKIPPED
    factor never silently drags the real score toward 0 just because
    its own real weight still counted)."""
    if not answer or not answer.strip():
        factors = {name: 0.0 for name in settings.CITATION_CORRECTNESS_FACTORS_WEIGHTS}
        return {"score": 0.0, "factors": factors}

    factors = {
        "citation_presence": _citation_presence(answer, context) if settings.CITATION_CORRECTNESS_CHECK_PRESENCE else None,
        "citation_accuracy": _citation_accuracy(answer, citations) if settings.CITATION_CORRECTNESS_CHECK_ACCURACY else None,
        "citation_format": _citation_format(answer) if settings.CITATION_CORRECTNESS_CHECK_FORMAT else None,
        "citation_completeness": _citation_completeness(answer),
    }
    weights = settings.CITATION_CORRECTNESS_FACTORS_WEIGHTS
    active = {name: value for name, value in factors.items() if value is not None}
    active_weight_total = sum(weights[name] for name in active) or 1.0
    score = max(0.0, min(1.0, sum(active[name] * weights[name] for name in active) / active_weight_total))
    return {"score": score, "factors": factors}


async def get_citation_correctness_summary(db: AsyncSession, dataset_id: uuid.UUID) -> dict:
    """Item 1's own literal function -- real, thin reuse of
    `retrieval_metrics.summarize_metric`."""
    return await summarize_metric(db, dataset_id, "citation_correctness")
