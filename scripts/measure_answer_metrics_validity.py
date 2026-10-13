"""Does each automatic answer-quality metric SEPARATE good answers from bad ones? Measured on LABELLED cases built from the real FastAPI corpus.

    python scripts/measure_answer_metrics_validity.py [--out answer_metrics_validity.json]

Cases (labels known by construction, NOT human judgements): for each of the 50 questions of data/test_set.json, the context is the corpus chunk that best matches the
reference answer.
  positive          the reference answer (written from the documentation) with that context
  easy negative     the reference answer of a question about ANOTHER topic, same context   (unsupported / off-topic)
  hard negative     the reference answer with one fact changed (an HTTP verb, a number, True/False), same context   (a plausible hallucination)
Reported per metric: mean score on each group and the AUROC "positive scores higher than negative" (0.5 = no discrimination, 1.0 = perfect). This proves what the metrics
can and cannot detect; it does not replace calibration against human labels (calibration/human_annotations.json is empty and needs a human)."""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SWAPS = [("POST", "DELETE"), ("GET", "PUT"), ("PUT", "GET"), ("DELETE", "POST"), ("True", "False"), ("False", "True"), ("200", "404"), ("201", "500")]


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def best_chunk(answer: str, chunks: list[dict], path: str) -> str:
    pool = [c for c in chunks if c.get("path") == path or c.get("doc_path") == path or path in json.dumps({k: c[k] for k in c if k != "content" and k != "text"})] or chunks
    target = tokens(answer)
    scored = sorted(pool, key=lambda c: len(target & tokens(c.get("content") or c.get("text") or "")), reverse=True)
    top = scored[0]
    return top.get("content") or top.get("text") or ""


def change_one_fact(answer: str) -> str | None:
    for old, new in SWAPS:
        if re.search(rf"\b{old}\b", answer):
            return re.sub(rf"\b{old}\b", new, answer, count=1)
    match = re.search(r"\b(\d+)\b", answer)
    if match:
        return answer[: match.start()] + str(int(match.group(1)) + 7) + answer[match.end():]
    return None


def auroc(positives: list[float], negatives: list[float]) -> float:
    if not positives or not negatives:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return round(wins / (len(positives) * len(negatives)), 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="answer_metrics_validity.json")
    args = ap.parse_args()
    from api.services.answer_quality_metrics import calculate_answer_relevance, calculate_faithfulness
    from api.services.context_relevance import calculate_context_relevance
    from api.services.contradiction_detection import find_contradiction

    questions = json.loads((ROOT / "data" / "test_set.json").read_text(encoding="utf-8"))
    chunks = json.loads((ROOT / "data" / "processed" / "chunks.json").read_text(encoding="utf-8"))
    cases = []
    for i, q in enumerate(questions):
        context = best_chunk(q["answer"], chunks, q["documents"][0])
        other = next(o for o in questions[i + 1:] + questions[:i] if o["topic"] != q["topic"])
        cases.append({"q": q["question"], "context": context, "good": q["answer"], "off_topic": other["answer"], "hard": change_one_fact(q["answer"]),
                      "wrong_context": best_chunk(other["answer"], chunks, other["documents"][0])})

    def faith(answer, context):
        return calculate_faithfulness(answer, [{"content": context}], context)["score"]

    groups = {
        "faithfulness": ([faith(c["good"], c["context"]) for c in cases], [faith(c["off_topic"], c["context"]) for c in cases], [faith(c["hard"], c["context"]) for c in cases if c["hard"]]),
        "answer_relevance": ([calculate_answer_relevance(c["q"], c["good"])["score"] for c in cases], [calculate_answer_relevance(c["q"], c["off_topic"])["score"] for c in cases],
                             [calculate_answer_relevance(c["q"], c["hard"])["score"] for c in cases if c["hard"]]),
        "context_relevance": ([calculate_context_relevance(c["q"], c["context"], [{"content": c["context"]}])["score"] for c in cases],
                              [calculate_context_relevance(c["q"], c["wrong_context"], [{"content": c["wrong_context"]}])["score"] for c in cases], []),
    }
    report = {}
    for name, (pos, easy, hard) in groups.items():
        report[name] = {"mean_positive": round(sum(pos) / len(pos), 3), "mean_easy_negative": round(sum(easy) / len(easy), 3) if easy else None,
                        "auroc_vs_easy_negative": auroc(pos, easy), "mean_hard_negative": round(sum(hard) / len(hard), 3) if hard else None,
                        "auroc_vs_hard_negative": auroc(pos[: len(hard)], hard) if hard else None, "n_positive": len(pos), "n_easy": len(easy), "n_hard": len(hard)}
    hard_cases = [c for c in cases if c["hard"]]
    detected = sum(1 for c in hard_cases if find_contradiction(c["hard"], c["context"]) is not None)
    clean = sum(1 for c in cases if find_contradiction(c["good"], c["context"]) is not None)
    report["contradiction_detection"] = {"hard_negatives_flagged": f"{detected}/{len(hard_cases)}", "positives_flagged_wrongly": f"{clean}/{len(cases)}"}
    Path(args.out).write_text(json.dumps({"labels": "constructed (not human)", "report": report}, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
