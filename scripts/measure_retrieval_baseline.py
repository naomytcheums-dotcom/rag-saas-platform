"""R-06 (retrieval part): Recall@k, MRR and NDCG of the platform's retrieval strategies on the REAL FastAPI documentation corpus, in-process, no answer generation.

The corpus must already be indexed in an organization of the local database (scripts/e2e_retrieval_baseline.py uploads it: one document per page, named with the page path
and "/" replaced by "__"). Questions: data/test_set.json (50 questions, 15 flagged `held_out`, reported separately).

    DATABASE_URL=<local asyncpg url> LLM_DEFAULT_PROVIDER=ollama ... python scripts/measure_retrieval_baseline.py --org <uuid> [--out retrieval_baseline.json]

Configurations: strategy (hybrid, vector_only, bm25_only, hybrid_reranked) x {default threshold 0.5 / top_k 5, threshold 0 / top_k 10}, plus hybrid with HyDE, with
multi-query and with MMR (these call the local LLM). A document counts as retrieved when one of its chunks is in the ranked list (ranked by first chunk position)."""

import argparse
import asyncio
import json
import math
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from local_only_guard import require_local_services  # noqa: E402

require_local_services()


def metrics(ranked_docs: list[str], expected: set[str]) -> dict[str, float]:
    out = {}
    for k in (1, 3, 5, 10):
        top = ranked_docs[:k]
        out[f"recall@{k}"] = len(expected & set(top)) / len(expected)
    rr = 0.0
    for position, doc in enumerate(ranked_docs, start=1):
        if doc in expected:
            rr = 1.0 / position
            break
    out["mrr"] = rr
    dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(ranked_docs[:10]) if d in expected)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(expected), 10)))
    out["ndcg@10"] = dcg / ideal if ideal else 0.0
    return out


async def main_async(args) -> int:
    from sqlalchemy import select

    from api.database import AsyncSessionLocal
    from api.models.document import Document
    from api.security.organization_settings import get_org_settings
    from api.services.retrieval_pipeline import search

    org = uuid.UUID(args.org)
    questions = json.loads((ROOT / "data" / "test_set.json").read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as db:
        docs = (await db.execute(select(Document.id, Document.name).where(Document.organization_id == org, Document.deleted_at.is_(None)))).all()
        by_name = {name: str(did) for did, name in docs}
        base = await get_org_settings(db, org)
        configs = []
        for strategy in ("hybrid", "vector_only", "bm25_only", "hybrid_reranked"):
            configs.append((f"{strategy} | default (threshold 0.5, top_k 5)", {"strategy": strategy}, {}))
            configs.append((f"{strategy} | no threshold, top_k 10", {"strategy": strategy, "top_k": 10, "score_threshold": 0.0}, {}))
        configs.append(("hybrid + HyDE | no threshold, top_k 10", {"strategy": "hybrid", "top_k": 10, "score_threshold": 0.0}, {"hyde_enabled": True}))
        configs.append(("hybrid + multi-query | no threshold, top_k 10", {"strategy": "hybrid", "top_k": 10, "score_threshold": 0.0}, {"multi_query_enabled": True}))
        configs.append(("hybrid + MMR | no threshold, top_k 10", {"strategy": "hybrid", "top_k": 10, "score_threshold": 0.0}, {"mmr_enabled": True}))
        report = {}
        usable = [q for q in questions if all(f"{p.replace('/', '__')}" in by_name for p in q["documents"])]
        print(f"documents in the organization: {len(by_name)}; usable questions: {len(usable)}/{len(questions)}", flush=True)
        for label, kwargs, flags in configs:
            started = time.time()
            per = {"all": [], "tuning": [], "held_out": []}
            for q in usable:
                expected = {by_name[p.replace("/", "__")] for p in q["documents"]}
                results = await search(db, org, q["question"], org_settings={**base, **flags}, **kwargs)
                ranked: list[str] = []
                for r in results:
                    if r["document_id"] not in ranked:
                        ranked.append(r["document_id"])
                m = metrics(ranked, expected)
                per["all"].append(m)
                per["held_out" if q.get("held_out") else "tuning"].append(m)
            report[label] = {"seconds": round(time.time() - started)}
            for split, rows in per.items():
                if rows:
                    report[label][split] = {k: round(sum(r[k] for r in rows) / len(rows), 3) for k in rows[0]} | {"n": len(rows)}
            print(f"{label}: {json.dumps(report[label]['all'])} ({report[label]['seconds']}s)", flush=True)
            Path(args.out).write_text(json.dumps({"corpus": "FastAPI docs", "questions": len(usable), "report": report, "generated": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--out", default="retrieval_baseline.json")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
