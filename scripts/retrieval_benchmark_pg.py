"""Retrieval benchmark on the REAL PostgreSQL + pgvector (HNSW) path.

Companion of `scripts/retrieval_benchmark.py` (portable numpy/BM25 path on SQLite). Here the production code
(`api.services.retrieval_pipeline.vector_search / bm25_search / hybrid_search`) runs against a real Postgres, so `vector_search` takes the
native `embedding_vector <=> query` ANN path through the HNSW index created by migration 0128.

Two measurements:
1. SCALE (`--docs 100,1000,10000`): latency percentiles, throughput and planted-source recall for one organization of N documents.
   Latency from a remote client includes the network round trips to the database; the server-side time of the ANN query is reported
   separately from `EXPLAIN (ANALYZE)`.
2. SHARED TABLE (`--crowd`, `--mid`): a mid-size organization shares the chunk table with others. An HNSW scan filtered by organization
   only looks at its `ef_search` best candidates BEFORE filtering, so without iterative scanning the tenant can get fewer than top_k results.
   The number of results and the recall against the exact top-k of its own vectors are measured.

SAFETY: the default target is the database named in the STAGING_DATABASE_URL environment variable, else in `.env.staging` (refused if its password is still a placeholder, or if it is the same
server/user as `.env`). `--target main --allow-main` uses the database named in `.env`; it then also refuses when the database is already
too full for the corpus (`--quota-mb`). Everything is written under organizations named exactly "Benchmark (throw-away)" and deleted at the
end -- also on failure; leftovers of an interrupted run are swept at the start. Vectors are random with planted neighbours and the text is
synthetic: latency/scale figures are meaningful, recall only validates the mechanics, not semantic quality.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DIM = 384
ORG_NAME = "Benchmark (throw-away)"
VOCAB = [f"w{n:04d}" for n in range(3000)]


def _server_identity(url: str) -> tuple[str, str]:
    parts = urlsplit(url.replace("postgresql+asyncpg://", "postgresql://"))
    return (parts.hostname or "", parts.username or "")


def _target_url(target: str, allow_main: bool) -> str:
    main = dotenv_values(ROOT / ".env").get("DATABASE_URL")
    if target == "main":
        if not allow_main:
            raise SystemExit("REFUSED: --target main needs --allow-main (it writes throw-away tenants into the main database).")
        if not main:
            raise SystemExit("REFUSED: .env has no DATABASE_URL")
        return main
    # The real staging URL may live only in the operator's own process environment (never in a file): that wins over .env.staging.
    staging = os.environ.get("STAGING_DATABASE_URL") or dotenv_values(ROOT / ".env.staging").get("DATABASE_URL")
    if not staging or re.search(r"//[^:]+:\[[^\]]*\]@", staging):
        raise SystemExit("REFUSED: .env.staging has no usable DATABASE_URL (the password is still a placeholder).")
    if main and _server_identity(staging) == _server_identity(main):
        raise SystemExit("REFUSED: .env.staging points at the same server/user as .env (the main database). Use --target main --allow-main if that is intended.")
    return staging


def _unit(vectors: np.ndarray) -> np.ndarray:
    return vectors / np.linalg.norm(vectors, axis=-1, keepdims=True)


def _near(center: np.ndarray, cosine: float, rng: np.random.Generator, count: int) -> np.ndarray:
    """`count` unit vectors whose cosine similarity to `center` is about `cosine`."""
    noise = _unit(rng.standard_normal((count, DIM)).astype("float32"))
    return _unit(cosine * center + np.sqrt(1.0 - cosine**2) * noise)


async def _create_org(sessions) -> uuid.UUID:
    from api.models.organization import Organization

    org_id = uuid.uuid4()
    async with sessions() as session:
        session.add(Organization(id=org_id, name=ORG_NAME, slug=f"bench-{uuid.uuid4().hex[:10]}"))
        await session.commit()
    return org_id


async def _insert_chunks(sessions, org_id, vectors: np.ndarray, chunks_per_doc: int, py_rng: random.Random) -> list[tuple[str, np.ndarray, list[str]]]:
    """Insert one document per `chunks_per_doc` vectors (both embedding columns, as production does). Returns (chunk_id, vector, words)."""
    from sqlalchemy import insert

    from api.models.document import Document, DocumentChunk

    planted = []
    docs, chunks = [], []

    async def flush():
        if docs:
            async with sessions() as session:
                await session.execute(insert(Document.__table__), docs)
                await session.execute(insert(DocumentChunk.__table__), chunks)
                await session.commit()
            docs.clear()
            chunks.clear()

    for start in range(0, len(vectors), chunks_per_doc):
        doc_id = uuid.uuid4()
        docs.append({"id": doc_id, "organization_id": org_id, "name": f"doc-{start}.pdf", "file_key": f"bench/{doc_id}.pdf",
                     "file_size": 1000, "file_type": "application/pdf", "status": "completed"})
        for offset, vector in enumerate(vectors[start:start + chunks_per_doc]):
            words = py_rng.choices(VOCAB, k=40)
            chunk_id = uuid.uuid4()
            chunks.append({"id": chunk_id, "document_id": doc_id, "organization_id": org_id, "content": " ".join(words),
                           "embedding": vector.tolist(), "embedding_vector": vector.tolist(), "embedding_dim": DIM,
                           "embedding_model": "synthetic", "chunk_index": offset})
            planted.append((str(chunk_id), vector, words))
        if len(docs) >= 100:
            await flush()
    await flush()
    return planted


async def _cleanup(sessions) -> None:
    """Delete every throw-away tenant (this run's and any interrupted earlier run's)."""
    from sqlalchemy import text

    async with sessions() as session:
        ids = [r[0] for r in (await session.execute(text("select id from organizations where name = :n"), {"n": ORG_NAME})).fetchall()]
        for org_id in ids:
            for table in ("document_chunks", "documents"):
                await session.execute(text(f"DELETE FROM {table} WHERE organization_id = :o"), {"o": org_id})
            await session.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        await session.commit()


async def _measure(sessions, org_id, planted, strategy, queries, concurrency, top_k, seed) -> dict:
    from api.services.retrieval_pipeline import bm25_search, hybrid_search, vector_search

    rng = random.Random(seed + 7)
    np_rng = np.random.default_rng(seed + 7)
    targets = [rng.choice(planted) for _ in range(queries)]
    latencies, errors, hits = [], [], 0
    semaphore = asyncio.Semaphore(concurrency)

    async def one(target):
        nonlocal hits
        chunk_id, vector, words = target
        noisy = vector + np_rng.standard_normal(DIM).astype("float32") * 0.02
        embedding = (noisy / np.linalg.norm(noisy)).tolist()
        text_query = " ".join(rng.sample(words, 4))
        async with semaphore:
            started = time.perf_counter()
            try:
                async with sessions() as session:
                    if strategy == "vector_only":
                        results = await vector_search(session, org_id, "q", top_k=top_k, query_embedding=embedding)
                    elif strategy == "bm25_only":
                        results = await bm25_search(session, org_id, text_query, top_k=top_k)
                    else:
                        results = await hybrid_search(session, org_id, text_query, top_k=top_k, query_embedding=embedding)
                latencies.append(time.perf_counter() - started)
                hits += any(r["chunk_id"] == chunk_id for r in results)
            except Exception as exc:  # noqa: BLE001 -- a failed query is a measured error
                errors.append(f"{type(exc).__name__}: {str(exc)[:160]}")

    wall = time.perf_counter()
    await asyncio.gather(*(one(t) for t in targets))
    wall = time.perf_counter() - wall
    ordered = sorted(latencies)

    def pct(f):
        return round(ordered[min(len(ordered) - 1, int(round(f * (len(ordered) - 1))))] * 1000, 1) if ordered else None

    return {"strategy": strategy, "concurrency": concurrency, "queries": queries, "errors": len(errors), "first_error": errors[0] if errors else None,
            "p50_ms": pct(0.5), "p95_ms": pct(0.95), "p99_ms": pct(0.99), "throughput_qps": round(len(latencies) / wall, 2) if wall else None,
            f"source_chunk_in_top_{top_k}": round(hits / queries, 3)}


async def _server_side_ann_ms(engine, org_id, planted, top_k) -> dict:
    """Server-side execution time of the ANN query (EXPLAIN ANALYZE), free of client/network time, and whether the HNSW index was used."""
    from sqlalchemy import text

    vector = "[" + ",".join(f"{x:.6f}" for x in planted[0][1].tolist()) + "]"
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "EXPLAIN (ANALYZE, FORMAT TEXT) SELECT id FROM document_chunks WHERE organization_id = :o AND embedding_vector IS NOT NULL "
            "ORDER BY embedding_vector <=> CAST(:v AS vector) LIMIT :k"), {"o": org_id, "v": vector, "k": top_k})).fetchall()
    plan = "\n".join(r[0] for r in rows)
    execution = re.search(r"Execution Time: ([0-9.]+) ms", plan)
    return {"uses_hnsw_index": "hnsw" in plan.lower(), "server_execution_ms": float(execution.group(1)) if execution else None}


async def _mid_tenant_in_a_big_table(sessions, engine, crowd_chunks: int, mid_chunks: int, top_k: int, seed: int) -> dict:
    """A mid-size tenant (`mid_chunks`) sharing the chunk table with other tenants (`crowd_chunks`). The planner picks the HNSW index when the
    tenant is only a few percent of the table, and an HNSW scan filtered by organization looks at its `ef_search` best candidates BEFORE
    the filter: the tenant then gets fewer than `top_k` results although it has plenty. Compared with the exact top-k of its own vectors."""
    from sqlalchemy import text

    from api.services.retrieval_pipeline import vector_search

    rng = np.random.default_rng(seed + 99)
    py_rng = random.Random(seed + 99)
    other_org, mid_org = await _create_org(sessions), await _create_org(sessions)
    await _insert_chunks(sessions, other_org, _unit(rng.standard_normal((crowd_chunks, DIM)).astype("float32")), 5, py_rng)
    mid_vectors = _unit(rng.standard_normal((mid_chunks, DIM)).astype("float32"))
    mid_planted = await _insert_chunks(sessions, mid_org, mid_vectors, 5, py_rng)
    async with engine.connect() as conn:
        await conn.execute(text("ANALYZE document_chunks"))
        await conn.commit()
    ids = [c[0] for c in mid_planted]

    full = recall_sum = results_sum = 0
    queries = 30
    for _ in range(queries):
        query = _unit(rng.standard_normal(DIM).astype("float32"))
        exact = {ids[i] for i in np.argsort(-(mid_vectors @ query))[:top_k]}
        async with sessions() as session:
            results = await vector_search(session, mid_org, "q", top_k=top_k, query_embedding=query.tolist())
        returned = {r["chunk_id"] for r in results}
        results_sum += len(results)
        full += len(results) == top_k
        recall_sum += len(returned & exact) / top_k
    async with engine.connect() as conn:
        vector = "[" + ",".join(f"{x:.6f}" for x in query.tolist()) + "]"
        plan = "\n".join(r[0] for r in (await conn.execute(text(
            "EXPLAIN SELECT id FROM document_chunks WHERE organization_id = :o AND embedding_vector IS NOT NULL "
            "ORDER BY embedding_vector <=> CAST(:v AS vector) LIMIT :k"), {"o": mid_org, "v": vector, "k": top_k})).fetchall())
    return {"other_tenants_chunks": crowd_chunks, "tenant_chunks": mid_chunks, "share_of_table_percent": round(100 * mid_chunks / (mid_chunks + crowd_chunks), 1),
            "planner_uses_hnsw": "hnsw" in plan.lower(), "queries": queries, "average_results_returned": round(results_sum / queries, 2), "top_k": top_k,
            "queries_with_full_top_k": full, "recall_vs_exact_top_k": round(recall_sum / queries, 3)}


async def main_async(args) -> dict:
    url = _target_url(args.target, args.allow_main)
    os.environ["DATABASE_URL"] = url
    os.environ["DATABASE_URL_TRANSACTION"] = url
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from api.config import settings

    if args.no_iterative_scan:
        settings.PGVECTOR_ITERATIVE_SCAN = False

    engine = create_async_engine(url, connect_args={"statement_cache_size": 0, "timeout": 60}, pool_size=6, max_overflow=2)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.connect() as conn:
        facts = {
            "revision": (await conn.execute(text("select version_num from alembic_version"))).scalar(),
            "pgvector": (await conn.execute(text("select extversion from pg_extension where extname='vector'"))).scalar(),
            "hnsw_indexes": [r[0] for r in (await conn.execute(text(
                "select indexname from pg_indexes where tablename='document_chunks' and indexdef ilike '%hnsw%'"))).fetchall()],
            "database_size_mb": int((await conn.execute(text("select pg_database_size(current_database())/1024/1024"))).scalar()),
            "iterative_scan_enabled_in_code": bool(getattr(settings, "PGVECTOR_ITERATIVE_SCAN", False)),
        }
    doc_counts = [int(x) for x in args.docs.split(",") if x.strip()]
    largest = max(doc_counts or [0])
    needed_mb = int(max(largest * args.chunks_per_doc, args.crowd) * 6.5 / 1024) + 1  # ~6.5 KB/chunk: JSON + vector + HNSW + text
    if args.target == "main" and facts["database_size_mb"] + needed_mb > 0.7 * args.quota_mb:
        raise SystemExit(f"REFUSED: the database is {facts['database_size_mb']} MB and this needs about {needed_mb} MB; the limit is 70% of {args.quota_mb} MB.")

    report = {"database": facts, "runs": [], "small_tenant": None}
    await _cleanup(sessions)
    try:
        if args.docs:
            for documents in doc_counts:
                org_id = await _create_org(sessions)
                started = time.perf_counter()
                rng = np.random.default_rng(args.seed)
                vectors = _unit(rng.standard_normal((documents * args.chunks_per_doc, DIM)).astype("float32"))
                planted = await _insert_chunks(sessions, org_id, vectors, args.chunks_per_doc, random.Random(args.seed))
                build = round(time.perf_counter() - started, 1)
                async with engine.connect() as conn:
                    await conn.execute(text("ANALYZE document_chunks"))
                    await conn.commit()
                run = {"documents": documents, "chunks": len(planted), "build_seconds": build,
                       "server_side_ann": await _server_side_ann_ms(engine, org_id, planted, args.top_k), "strategies": []}
                for strategy in ("vector_only", "bm25_only", "hybrid"):
                    for concurrency in [int(x) for x in args.concurrency.split(",")]:
                        run["strategies"].append(await _measure(sessions, org_id, planted, strategy, args.queries, concurrency, args.top_k, args.seed))
                report["runs"].append(run)
                await _cleanup(sessions)
        if args.crowd:
            report["small_tenant"] = await _mid_tenant_in_a_big_table(sessions, engine, args.crowd, args.mid, args.top_k, args.seed)
    finally:
        await _cleanup(sessions)
        await engine.dispose()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docs", default="100,1000", help="comma-separated document counts for the scale measurement ('' to skip)")
    parser.add_argument("--chunks-per-doc", type=int, default=5)
    parser.add_argument("--queries", type=int, default=30)
    parser.add_argument("--concurrency", default="1,4")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--crowd", type=int, default=0, help="chunks of the OTHER tenants in the shared-table scenario (0 = skip)")
    parser.add_argument("--mid", type=int, default=1500, help="chunks of the tenant under test in the shared-table scenario")
    parser.add_argument("--no-iterative-scan", action="store_true", help="measure with PGVECTOR_ITERATIVE_SCAN switched off")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--target", choices=("staging", "main"), default="staging")
    parser.add_argument("--allow-main", action="store_true", help="required with --target main")
    parser.add_argument("--quota-mb", type=int, default=500, help="the database's size limit (Supabase free plan: 500)")
    args = parser.parse_args()
    report = asyncio.run(main_async(args))
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print("database:", report["database"])
    for run in report["runs"]:
        print(f"\n== {run['documents']} documents / {run['chunks']} chunks (built in {run['build_seconds']}s) -- server-side ANN: {run['server_side_ann']} ==")
        for s in run["strategies"]:
            print(f"  {s['strategy']:11} c={s['concurrency']}  p50={s['p50_ms']}ms p95={s['p95_ms']}ms p99={s['p99_ms']}ms  {s['throughput_qps']} q/s  "
                  f"recall@top={s[f'source_chunk_in_top_{args.top_k}']}  errors={s['errors']}" + (f"  first_error={s['first_error']}" if s["errors"] else ""))
    if report["small_tenant"]:
        print("\n== mid-size tenant sharing the table ==", report["small_tenant"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
