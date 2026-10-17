"""SQuAD 2.0 adapter and answer-level metrics for the RAG evaluation protocol (Lot E). Pure functions, no network, no database.

SQuAD 2.0 format (v2.0): {"version": "v2.0", "data": [{"title", "paragraphs": [{"context", "qas": [{"id", "question", "is_impossible",
"answers": [{"text", "answer_start"}], "plausible_answers": [...]}]}]}]}. Impossible questions have NO gold answer: the right behaviour is to abstain.

What this module gives (and what it does not):
* `load_squad` validates the structure and flattens it into questions and contexts, keeping every SQuAD id and EVERY gold answer (the official
  EM/F1 take the best score over all gold answers).
* Each distinct context becomes ONE corpus document with a stable key (sha256 of title + context): `corpus_documents` is what to ingest,
  `questions_for_import` produces the Eval Lab import rows once you know the real document ids (key -> id), so the dataset's `document_id`
  always points to a document that exists. A question whose context was not ingested raises: no silent drop.
* Metrics: official SQuAD answer normalization, exact match, token F1, best-over-gold, abstention precision/recall, `citation_support`
  (a citation counts only if the cited passage CONTAINS a gold answer: pointing at the right document is not enough).
* Retrieval metrics (Recall@k, MRR, NDCG) stay in api/services/retrieval_metrics.py: the dataset rows built here use its
  `expected_documents=[{"document_id", "relevance_score"}]` format.
It does NOT download SQuAD, call a model or compute any benchmark number. SQuAD 2.0 is a Wikipedia reading-comprehension benchmark: it says
nothing about enterprise documents (tables, PDFs, OCR, multilingual content, access control): see docs/evaluation/RAG_EVALUATION.md."""

import hashlib
import re
import string
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

UNANSWERABLE_CATEGORY = "squad2:unanswerable"
ANSWERABLE_CATEGORY = "squad2:answerable"


class SquadFormatError(ValueError):
    pass


@dataclass(frozen=True)
class SquadQuestion:
    squad_id: str
    question: str
    gold_answers: tuple[str, ...]
    is_impossible: bool
    context_key: str
    title: str


@dataclass(frozen=True)
class SquadCorpus:
    questions: tuple[SquadQuestion, ...]
    contexts: Mapping[str, tuple[str, str]] = field(default_factory=dict)  # key -> (title, context)


def context_key(title: str, context: str) -> str:
    return hashlib.sha256(f"{title}\n{context}".encode("utf-8")).hexdigest()[:24]


def document_name(key: str) -> str:
    return f"squad2::{key}"


def load_squad(data: dict) -> SquadCorpus:
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise SquadFormatError("not a SQuAD file: missing the 'data' list")
    version = str(data.get("version", ""))
    if not version.startswith("v2"):
        raise SquadFormatError(f"expected SQuAD v2.x (with unanswerable questions), got version {version!r}")
    questions, contexts, seen = [], {}, set()
    for article in data["data"]:
        title = str(article.get("title", ""))
        for paragraph in article.get("paragraphs", []):
            context = paragraph.get("context")
            if not isinstance(context, str) or not context.strip():
                raise SquadFormatError(f"article {title!r}: a paragraph has no context")
            key = context_key(title, context)
            contexts[key] = (title, context)
            for qa in paragraph.get("qas", []):
                squad_id, text = qa.get("id"), qa.get("question")
                if not squad_id or not text:
                    raise SquadFormatError(f"article {title!r}: a question has no id or no text")
                if squad_id in seen:
                    raise SquadFormatError(f"duplicate SQuAD id {squad_id!r}")
                seen.add(squad_id)
                impossible = bool(qa.get("is_impossible", False))
                answers = tuple(dict.fromkeys(a["text"] for a in qa.get("answers", []) if a.get("text")))
                if impossible and answers:
                    raise SquadFormatError(f"{squad_id}: is_impossible=true but gold answers are present")
                if not impossible and not answers:
                    raise SquadFormatError(f"{squad_id}: answerable question without a gold answer")
                questions.append(SquadQuestion(squad_id, text, answers, impossible, key, title))
    if not questions:
        raise SquadFormatError("no question found")
    return SquadCorpus(tuple(questions), contexts)


def corpus_documents(corpus: SquadCorpus) -> list[dict]:
    """One document per distinct context: ingest these (name = squad2::<key>) to obtain real document ids."""
    return [{"key": key, "name": document_name(key), "title": title, "text": context} for key, (title, context) in sorted(corpus.contexts.items())]


def questions_for_import(corpus: SquadCorpus, document_ids: Mapping[str, str]) -> list[dict]:
    """Rows for the Eval Lab JSON import. `document_ids` maps context key -> the REAL document id after ingestion."""
    rows = []
    for item in corpus.questions:
        row = {"question": item.question, "category": UNANSWERABLE_CATEGORY if item.is_impossible else ANSWERABLE_CATEGORY}
        if item.is_impossible:
            row["expected_answer"] = None
            row["expected_documents"] = []  # nothing to retrieve: the system must abstain
        else:
            if item.context_key not in document_ids:
                raise SquadFormatError(f"{item.squad_id}: its context was not ingested (no real document id): refusing to build a dataset that points nowhere")
            row["expected_answer"] = item.gold_answers[0]
            row["expected_documents"] = [{"document_id": str(document_ids[item.context_key]), "relevance_score": 1.0}]
        rows.append(row)
    return rows


# -- metrics (official SQuAD v2.0 evaluation semantics) ---------------------------------------------------------------------

def normalize_answer(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def exact_match(prediction: str, gold: str) -> float:
    return float(normalize_answer(prediction) == normalize_answer(gold))


def f1_score(prediction: str, gold: str) -> float:
    predicted, expected = normalize_answer(prediction).split(), normalize_answer(gold).split()
    if not predicted or not expected:
        return float(predicted == expected)  # both empty (both "no answer") = 1, one empty = 0
    common = Counter(predicted) & Counter(expected)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision, recall = overlap / len(predicted), overlap / len(expected)
    return 2 * precision * recall / (precision + recall)


def best_over_golds(metric, prediction: str, golds: Iterable[str]) -> float:
    golds = list(golds) or [""]
    return max(metric(prediction, gold) for gold in golds)


def citation_support(cited_passages: Iterable[str], gold_answers: Iterable[str]) -> bool:
    """True only when a cited passage CONTAINS a gold answer (normalized). A citation to the right document that does not contain the answer is not support."""
    golds = [normalize_answer(g) for g in gold_answers if g and normalize_answer(g)]
    passages = [normalize_answer(p) for p in cited_passages]
    return any(gold in passage for gold in golds for passage in passages)


def score_predictions(corpus: SquadCorpus, predictions: Mapping[str, Mapping]) -> dict:
    """predictions: squad_id -> {"answer": str, "abstained": bool}. A missing prediction is an ERROR (never silently scored as an abstention)."""
    missing = [q.squad_id for q in corpus.questions if q.squad_id not in predictions]
    if missing:
        raise SquadFormatError(f"{len(missing)} question(s) have no prediction, e.g. {missing[:3]}")
    has_em, has_f1, no_ok, tp, fp, fn = [], [], [], 0, 0, 0
    for q in corpus.questions:
        p = predictions[q.squad_id]
        abstained = bool(p.get("abstained")) or not str(p.get("answer", "")).strip()
        answer = "" if abstained else str(p["answer"])
        if q.is_impossible:
            no_ok.append(float(abstained))
            tp += abstained
            fn += not abstained
        else:
            has_em.append(best_over_golds(exact_match, answer, q.gold_answers))
            has_f1.append(best_over_golds(f1_score, answer, q.gold_answers))
            fp += abstained  # abstained although an answer existed
    mean = lambda xs: (sum(xs) / len(xs)) if xs else None  # noqa: E731
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else (0.0 if precision == 0 or recall == 0 else None)
    total = len(corpus.questions)
    overall_em = (sum(has_em) + sum(no_ok)) / total
    overall_f1 = (sum(has_f1) + sum(no_ok)) / total
    return {
        "questions": total, "answerable": len(has_em), "unanswerable": len(no_ok),
        "HasAns_exact": mean(has_em), "HasAns_f1": mean(has_f1), "NoAns_accuracy": mean(no_ok),
        "exact": overall_em, "f1": overall_f1,
        "abstention_precision": precision, "abstention_recall": recall, "abstention_f1": f1,
    }
