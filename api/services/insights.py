"""Specs 11.2.5, 11.2.7-11.2.10, 11.2.14-11.2.16, 15.2.5, 15.2.6 -- what the users of an organization ask, where the knowledge base fails them, and how to fix it.

Everything is computed on demand from data that already exists (conversation messages, feedback, citations, documents) and is scoped to one organization.
No LLM is called: questions are grouped by word overlap (Jaccard similarity), so clusters are lexical, not semantic. That is a deliberate, cheap and
reproducible first version; swapping `cluster_questions` for an embedding-based grouping would not change the callers.
"""

import datetime as dt
import re
import unicodedata
import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.billing import CreditTransaction, CreditTransactionType
from api.models.citation import Citation
from api.models.conversation import Conversation, ConversationMessage
from api.models.document import Document
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.message_actions import MessageFeedback
from api.models.response import Response
from api.models.user import User

_MAX_MESSAGES = 20000
_REFUSAL_MARKERS = (
    "i don't know", "i do not know", "i cannot find", "i couldn't find", "no information", "not enough information", "cannot answer",
    "je ne sais pas", "je n'ai pas trouve", "je ne trouve pas", "pas d'information", "aucune information", "impossible de repondre",
    "no lo se", "no sé", "no se", "no he encontrado", "no tengo informacion", "ich weiss nicht", "ich weiß nicht", "keine informationen",
    "nao sei", "não sei", "nao encontrei", "não encontrei", "sem informacao",
)
_STOPWORDS = frozenset(
    "the a an of to in on for and or is are was were be what how why when where who which do does did can could i you we it this that with from at by "
    "le la les un une des du de et ou est sont que qui quoi comment pourquoi quand ou dans sur pour par avec ce cet cette ces mon ma mes ton ta tes "
    "el los las y es son que como por para con una unos der die das und ist sind wie was o os em um uma".split()
)


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalize_question(text: str) -> str:
    text = _strip_accents(text.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def keywords(text: str) -> frozenset[str]:
    return frozenset(w for w in normalize_question(text).split() if len(w) > 2 and w not in _STOPWORDS)


def is_refusal(answer: str | None) -> bool:
    if not answer:
        return False
    lowered = answer.lower()
    flat = _strip_accents(lowered)
    return any(marker in lowered or _strip_accents(marker) in flat for marker in _REFUSAL_MARKERS)


async def load_question_answer_pairs(db: AsyncSession, org_id: uuid.UUID, days: int = 30) -> list[dict]:
    """Every user question of the organization in the last `days` days, with the assistant reply that followed it and the ratings that reply received."""
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = (await db.execute(
        select(ConversationMessage.id, ConversationMessage.conversation_id, ConversationMessage.role, ConversationMessage.content, ConversationMessage.created_at)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.organization_id == org_id, Conversation.deleted_at.is_(None), ConversationMessage.created_at >= since,
               ConversationMessage.role.in_(("user", "assistant")))
        .order_by(ConversationMessage.conversation_id, ConversationMessage.created_at).limit(_MAX_MESSAGES)
    )).all()
    ratings: dict[uuid.UUID, list[str]] = {}
    assistant_ids = [r.id for r in rows if r.role == "assistant"]
    if assistant_ids:
        for message_id, rating in (await db.execute(select(MessageFeedback.message_id, MessageFeedback.rating).where(MessageFeedback.message_id.in_(assistant_ids)))).all():
            ratings.setdefault(message_id, []).append(rating)
    pairs: list[dict] = []
    pending: dict | None = None
    current_conversation = None
    for row in rows:
        if row.conversation_id != current_conversation:
            current_conversation, pending = row.conversation_id, None
        if row.role == "user":
            pending = {"question": row.content, "message_id": row.id, "conversation_id": row.conversation_id, "created_at": row.created_at,
                       "answer": None, "answer_id": None, "ratings": []}
            pairs.append(pending)
        elif pending is not None and pending["answer_id"] is None:
            pending["answer"], pending["answer_id"], pending["ratings"] = row.content, row.id, ratings.get(row.id, [])
    return pairs


def most_asked(pairs: list[dict], top_n: int = 10) -> list[dict]:
    counts: Counter[str] = Counter()
    example: dict[str, str] = {}
    for pair in pairs:
        key = normalize_question(pair["question"])
        if key:
            counts[key] += 1
            example.setdefault(key, pair["question"])
    return [{"question": example[key], "count": count} for key, count in counts.most_common(top_n)]


def failed_questions(pairs: list[dict]) -> list[dict]:
    """A question failed when the answer is a refusal ("I do not know"), or the answer received a thumbs down."""
    failed = []
    for pair in pairs:
        if pair["answer_id"] is None:
            continue
        reasons = []
        if is_refusal(pair["answer"]):
            reasons.append("no_answer")
        if "negative" in pair["ratings"]:
            reasons.append("thumbs_down")
        if reasons:
            failed.append({"question": pair["question"], "reasons": reasons, "message_id": pair["message_id"], "created_at": pair["created_at"]})
    return failed


def retrieval_success_rate(pairs: list[dict]) -> dict:
    answered = [p for p in pairs if p["answer_id"] is not None]
    refused = sum(1 for p in answered if is_refusal(p["answer"]))
    total = len(answered)
    return {"answered_questions": total, "refused": refused, "success_rate": round((total - refused) / total, 4) if total else None}


def cluster_questions(questions: list[str], threshold: float = 0.5) -> list[dict]:
    """Greedy grouping of questions that share at least `threshold` of their keywords (Jaccard). Largest groups first."""
    clusters: list[dict] = []
    for question in questions:
        words = keywords(question)
        if not words:
            continue
        best, best_score = None, 0.0
        for cluster in clusters:
            union = len(words | cluster["words"])
            score = len(words & cluster["words"]) / union if union else 0.0
            if score > best_score:
                best, best_score = cluster, score
        if best is not None and best_score >= threshold:
            best["questions"].append(question)
            best["words"] = best["words"] | words
        else:
            clusters.append({"words": set(words), "questions": [question]})
    result = []
    for cluster in clusters:
        counts = Counter(normalize_question(q) for q in cluster["questions"])
        label_key = counts.most_common(1)[0][0]
        label = next(q for q in cluster["questions"] if normalize_question(q) == label_key)
        top_words = [w for w, _ in Counter(w for q in cluster["questions"] for w in keywords(q)).most_common(5)]
        result.append({"label": label, "size": len(cluster["questions"]), "keywords": top_words, "examples": cluster["questions"][:3]})
    return sorted(result, key=lambda c: (-c["size"], c["label"]))


def knowledge_gaps(pairs: list[dict], min_count: int = 2) -> list[dict]:
    """Groups of similar questions the knowledge base keeps failing on (refusals or thumbs down)."""
    failed = [f["question"] for f in failed_questions(pairs)]
    return [c for c in cluster_questions(failed) if c["size"] >= min_count]


async def documentation_gap_report(db: AsyncSession, org_id: uuid.UUID, pairs: list[dict], min_count: int = 2) -> list[dict]:
    """For each knowledge gap: what to document, how often users asked, example questions, and whether a document with a related name already exists."""
    names = [(row.name or "") for row in (await db.execute(select(Document.name).where(Document.organization_id == org_id))).all()]
    normalized_names = [normalize_question(n) for n in names]
    report = []
    for gap in knowledge_gaps(pairs, min_count):
        related = sorted({n for n, norm in zip(names, normalized_names) if any(k in norm for k in gap["keywords"])})[:5]
        report.append({
            "suggested_topic": ", ".join(gap["keywords"]) or gap["label"], "times_asked": gap["size"], "example_questions": gap["examples"],
            "related_documents": related, "status": "partially_covered" if related else "missing",
        })
    return report


async def document_usage(db: AsyncSession, org_id: uuid.UUID, days: int = 30) -> list[dict]:
    """How often each document was cited, with the average relevance of those citations."""
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = (await db.execute(
        select(Citation.document_id, func.count(Citation.id), func.avg(Citation.relevance_score))
        .join(Response, Response.id == Citation.response_id)
        .where(Response.organization_id == org_id, Citation.document_id.is_not(None), Citation.created_at >= since)
        .group_by(Citation.document_id)
    )).all()
    names = {}
    if rows:
        names = {d.id: d.name for d in (await db.execute(select(Document.id, Document.name).where(Document.id.in_([r[0] for r in rows])))).all()}
    return [{"document_id": r[0], "name": names.get(r[0]), "citations": r[1], "average_relevance": round(float(r[2] or 0.0), 4)} for r in rows]


def top_documents(usage: list[dict], limit: int = 10) -> list[dict]:
    return sorted(usage, key=lambda d: (-d["citations"], -d["average_relevance"]))[:limit]


def worst_documents(usage: list[dict], limit: int = 10, min_citations: int = 2) -> list[dict]:
    """Documents that are cited but with the lowest average relevance (noise in the knowledge base)."""
    return sorted([d for d in usage if d["citations"] >= min_citations], key=lambda d: (d["average_relevance"], -d["citations"]))[:limit]


# ----- live-feedback failure analysis (15.2.5) and feedback -> evaluation cases (15.2.6)

def classify_feedback_reason(reason: str | None, comment: str | None = None) -> str:
    """Map a free-text reason to the Eval Lab failure categories."""
    text = _strip_accents(f"{reason or ''} {comment or ''}".lower())
    if any(w in text for w in ("hallucin", "invent", "made up", "fabricat", "inexact", "false", "faux")):
        return "GENERATION_HALLUCINATION"
    if any(w in text for w in ("incomplete", "incomplet", "partial", "missing", "manque", "truncated")):
        return "GENERATION_INCOMPLETE"
    if any(w in text for w in ("source", "document", "irrelevant", "pertinent", "wrong doc", "not found", "retriev")):
        return "RETRIEVAL_FAILURE"
    return "OTHER"


async def feedback_failure_analysis(db: AsyncSession, org_id: uuid.UUID, days: int = 90) -> dict:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = (await db.execute(
        select(MessageFeedback.reason, MessageFeedback.comment)
        .join(ConversationMessage, ConversationMessage.id == MessageFeedback.message_id)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.organization_id == org_id, MessageFeedback.rating == "negative", MessageFeedback.created_at >= since)
    )).all()
    counts = Counter(classify_feedback_reason(r.reason, r.comment) for r in rows)
    return {"negative_feedback": len(rows), "by_category": dict(counts)}


async def feedback_to_evaluation_cases(db: AsyncSession, org_id: uuid.UUID, dataset_id: uuid.UUID, only_with_correction: bool = False, days: int = 90) -> dict:
    """Turn thumbs-down answers into questions of an evaluation dataset (question = the user's question, expected answer = the user's correction when given)."""
    dataset = await db.get(EvaluationDataset, dataset_id)
    if dataset is None or dataset.organization_id != org_id:
        raise LookupError("dataset not found")
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    negatives = (await db.execute(
        select(MessageFeedback.message_id, MessageFeedback.correction, MessageFeedback.reason)
        .join(ConversationMessage, ConversationMessage.id == MessageFeedback.message_id)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.organization_id == org_id, MessageFeedback.rating == "negative", MessageFeedback.created_at >= since)
    )).all()
    existing = {normalize_question(q) for q in (await db.scalars(select(EvaluationQuestion.question).where(EvaluationQuestion.dataset_id == dataset_id))).all()}
    created = skipped = 0
    for message_id, correction, reason in negatives:
        if only_with_correction and not correction:
            skipped += 1
            continue
        answer_message = await db.get(ConversationMessage, message_id)
        previous = await db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == answer_message.conversation_id, ConversationMessage.role == "user",
                ConversationMessage.created_at <= answer_message.created_at,
            ).order_by(ConversationMessage.created_at.desc()).limit(1)
        )
        if previous is None or normalize_question(previous.content) in existing:
            skipped += 1
            continue
        db.add(EvaluationQuestion(
            dataset_id=dataset_id, question=previous.content, expected_answer=correction, category="from_feedback",
            metadata_json={"source": "user_feedback", "feedback_category": classify_feedback_reason(reason)},
        ))
        existing.add(normalize_question(previous.content))
        created += 1
    await db.flush()
    return {"created": created, "skipped": skipped}


# ----- spec 11.2.12 / 11.2.13: cost per user and per answer, in AI credits (organizations that bring their own provider key consume no credits and show 0)

async def cost_per_user(db: AsyncSession, org_id: uuid.UUID, days: int = 30) -> list[dict]:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = (await db.execute(
        select(CreditTransaction.user_id, User.email, func.count(CreditTransaction.id), func.coalesce(func.sum(-CreditTransaction.amount), 0))
        .join(User, User.id == CreditTransaction.user_id, isouter=True)
        .where(CreditTransaction.organization_id == org_id, CreditTransaction.type == CreditTransactionType.consume, CreditTransaction.created_at >= since)
        .group_by(CreditTransaction.user_id, User.email)
    )).all()
    return sorted(
        [{"user_id": r[0], "email": r[1], "operations": r[2], "credits_spent": int(r[3])} for r in rows], key=lambda x: -x["credits_spent"],
    )


async def cost_per_answer(db: AsyncSession, org_id: uuid.UUID, days: int = 30) -> dict:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    spent = int(await db.scalar(
        select(func.coalesce(func.sum(-CreditTransaction.amount), 0)).where(
            CreditTransaction.organization_id == org_id, CreditTransaction.type == CreditTransactionType.consume, CreditTransaction.created_at >= since,
        )
    ) or 0)
    operations = int(await db.scalar(
        select(func.count(CreditTransaction.id)).where(
            CreditTransaction.organization_id == org_id, CreditTransaction.type == CreditTransactionType.consume, CreditTransaction.created_at >= since,
        )
    ) or 0)
    return {"credits_spent": spent, "billed_operations": operations, "credits_per_operation": round(spent / operations, 4) if operations else None}

