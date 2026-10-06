"""Real retrieval benchmark at 100 / 1,000 / 10,000 documents (Hardening Mission, §7).

Measures the PRODUCTION retrieval code (`api.services.retrieval_pipeline`:
`vector_search`, `bm25_search`, `hybrid_search`) against a synthetic corpus held in a
TEMPORARY local SQLite file -- never the real database -- and reports, per corpus
size and strategy: p50 / p95 / p99 latency, throughput at the chosen concurrency, a
measured recall of the exact source chunk, errors, and process memory.

What this does and does NOT measure -- read before quoting a number:
- It exercises the portable (numpy / in-process BM25) path, i.e. what runs on SQLite, on
  non-default embedding dimensions and when PGVECTOR_ENABLED=False. It does NOT measure the
  PostgreSQL pgvector/HNSW path (needs a Postgres with pgvector; see `--postgres-note`).
- Vectors are random unit vectors with a planted nearest neighbour; BM25 text is synthetic.
  Latency/scale numbers are meaningful; recall here validates the search MECHANICS (an exact
  search must find the planted source chunk), it says nothing about semantic quality on real
  documents -- that is the Eval Lab's job.
- Large corpora are refused by default (`--max-chunks`) because the portable path loads every
  chunk of the organization per query; pass `--force-large` only on a machine with the RAM.

Usage:
    python scripts/retrieval_benchmark.py --docs 100,1000 --queries 40 --concurrency 1,4
    python scripts/retrieval_benchmark.py --docs 100,1000,10000 --force-large --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DIM = 384
MEMORY_DB = ":memory-shared:"
CHUNKS_PER_DOC = 5
VOCAB = [f"w{n:04d}" for n in range(3000)]


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return float("nan")
    index = min(len(sorted_values) - 1, max(0, int(round(fraction * (len(sorted_values) - 1)))))
    return sorted_values[index]


def _rss_mb() -> float:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 -- memory reporting is best-effort
        return float("nan")


async def _build_corpus(db_path: str, documents: int, seed: int) -> dict:
    from sqlalchemy import insert
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from api.database import Base
    import api.models  # noqa: F401 -- registers every table on Base.metadata
    from api.models.document import Document, DocumentChunk
    from api.models.organization import Organization

    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)
    anchor = None
    if db_path == MEMORY_DB:
        # A shared-cache in-memory database: no disk I/O at all (a slow disk -- an SD card or a USB stick -- turns the corpus build into
        # hours), still visible to every connection of the process. One "anchor" connection keeps it alive.
        engine = create_async_engine("sqlite+aiosqlite:///file:ragbench?mode=memory&cache=shared&uri=true")
        anchor = await engine.connect()
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    org_id = uuid.uuid4()
    async with sessions() as session:
        session.add(Organization(id=org_id, name="Benchmark Org", slug=f"bench-{uuid.uuid4().hex[:8]}"))
        await session.commit()

    doc_rows, chunk_rows, planted = [], [], []
    for d in range(documents):
        doc_id = uuid.uuid4()
        doc_rows.append({"id": doc_id, "organization_id": org_id, "name": f"doc-{d}.pdf", "file_key": f"bench/{doc_id}.pdf",
                         "file_size": 1000, "file_type": "application/pdf", "status": "completed"})
        vectors = rng.standard_normal((CHUNKS_PER_DOC, DIM)).astype("float32")
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        for c in range(CHUNKS_PER_DOC):
            words = py_rng.choices(VOCAB, k=40)
            chunk_id = uuid.uuid4()
            chunk_rows.append({
                "id": chunk_id, "document_id": doc_id, "organization_id": org_id, "content": " ".join(words),
                "embedding": vectors[c].tolist(), "embedding_dim": DIM, "embedding_model": "synthetic", "chunk_index": c,
            })
            planted.append((str(chunk_id), vectors[c], words))

    async with sessions() as session:
        for i in range(0, len(doc_rows), 500):
            await session.execute(insert(Document.__table__), doc_rows[i:i + 500])
        for i in range(0, len(chunk_rows), 500):
            await session.execute(insert(DocumentChunk.__table__), chunk_rows[i:i + 500])
        await session.commit()
    return {"engine": engine, "sessions": sessions, "org_id": org_id, "planted": planted, "anchor": anchor}


async def _run_strategy(corpus: dict, strategy: str, queries: int, concurrency: int, top_k: int, seed: int) -> dict:
    from api.services.retrieval_pipeline import bm25_search, hybrid_search, vector_search

    rng = random.Random(seed + 7)
    np_rng = np.random.default_rng(seed + 7)
    targets = [rng.choice(corpus["planted"]) for _ in range(queries)]
    latencies: list[float] = []
    hits = 0
    errors: list[str] = []
    semaphore = asyncio.Semaphore(concurrency)

    async def one(target) -> None:
        nonlocal hits
        chunk_id, vector, words = target
        noisy = vector + np_rng.standard_normal(DIM).astype("float32") * 0.02
        embedding = (noisy / np.linalg.norm(noisy)).tolist()
        text_query = " ".join(rng.sample(words, 4))
        async with semaphore:
            started = time.perf_counter()
            try:
                async with corpus["sessions"]() as session:
                    if strategy == "vector_only":
                        results = await vector_search(session, corpus["org_id"], "q", top_k=top_k, query_embedding=embedding)
                    elif strategy == "bm25_only":
                        results = await bm25_search(session, corpus["org_id"], text_query, top_k=top_k)
                    else:
                        results = await hybrid_search(session, corpus["org_id"], text_query, top_k=top_k, query_embedding=embedding)
                latencies.append(time.perf_counter() - started)
                hits += any(r["chunk_id"] == chunk_id for r in results)
            except Exception as exc:  # noqa: BLE001 -- a failed query is a measured error, not a crash
                errors.append(f"{type(exc).__name__}: {exc}")

    wall = time.perf_counter()
    await asyncio.gather(*(one(t) for t in targets))
    wall = time.perf_counter() - wall
    ordered = sorted(latencies)
    return {
        "strategy": strategy, "concurrency": concurrency, "queries": queries, "errors": len(errors), "first_error": errors[0] if errors else None,
        "p50_ms": round(_percentile(ordered, 0.50) * 1000, 1), "p95_ms": round(_percentile(ordered, 0.95) * 1000, 1),
        "p99_ms": round(_percentile(ordered, 0.99) * 1000, 1), "mean_ms": round(statistics.fmean(ordered) * 1000, 1) if ordered else None,
        "throughput_qps": round(len(latencies) / wall, 2) if wall else None, f"source_chunk_in_top_{top_k}": round(hits / queries, 3),
    }


async def main_async(args) -> dict:
    report = {"dimension": DIM, "chunks_per_document": CHUNKS_PER_DOC, "path": "portable (numpy / in-process BM25) on SQLite", "corpora": []}
    for documents in [int(x) for x in args.docs.split(",")]:
        chunks = documents * CHUNKS_PER_DOC
        entry: dict = {"documents": documents, "chunks": chunks}
        if chunks > args.max_chunks and not args.force_large:
            entry["skipped"] = f"{chunks} chunks exceeds --max-chunks={args.max_chunks} (the portable path loads every chunk per query); rerun with --force-large on a machine with enough RAM"
            report["corpora"].append(entry)
            continue
        with tempfile.TemporaryDirectory(prefix="rag-bench-") as workdir:
            started = time.perf_counter()
            corpus = await _build_corpus(MEMORY_DB if args.memory else str(Path(workdir) / "bench.db"), documents, args.seed)
            entry["build_seconds"] = round(time.perf_counter() - started, 1)
            entry["rss_mb_after_build"] = round(_rss_mb(), 0)
            entry["runs"] = []
            for strategy in ("vector_only", "bm25_only", "hybrid"):
                for concurrency in [int(c) for c in args.concurrency.split(",")]:
                    entry["runs"].append(await _run_strategy(corpus, strategy, args.queries, concurrency, args.top_k, args.seed))
            entry["rss_mb_peak_after_queries"] = round(_rss_mb(), 0)
            if corpus["anchor"] is not None:
                await corpus["anchor"].close()
            await corpus["engine"].dispose()
        report["corpora"].append(entry)
    return report


def _print_table(report: dict) -> None:
    print(f"\nPath: {report['path']}  |  {report['dimension']}-d vectors, {report['chunks_per_document']} chunks/document")
    for corpus in report["corpora"]:
        print(f"\n== {corpus['documents']} documents / {corpus['chunks']} chunks ==")
        if "skipped" in corpus:
            print("  SKIPPED:", corpus["skipped"])
            continue
        print(f"  build {corpus['build_seconds']}s, RSS {corpus['rss_mb_after_build']} MB -> {corpus['rss_mb_peak_after_queries']} MB")
        print(f"  {'strategy':<12}{'conc':>5}{'p50 ms':>10}{'p95 ms':>10}{'p99 ms':>10}{'qps':>8}{'recall':>8}{'err':>5}")
        for run in corpus["runs"]:
            recall = [v for k, v in run.items() if k.startswith("source_chunk_in_top_")][0]
            print(f"  {run['strategy']:<12}{run['concurrency']:>5}{run['p50_ms']:>10}{run['p95_ms']:>10}{run['p99_ms']:>10}{run['throughput_qps']:>8}{recall:>8}{run['errors']:>5}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docs", default="100,1000,10000", help="comma-separated document counts")
    parser.add_argument("--queries", type=int, default=40)
    parser.add_argument("--concurrency", default="1,4")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-chunks", type=int, default=10_000, help="refuse corpora larger than this many chunks unless --force-large")
    parser.add_argument("--force-large", action="store_true")
    parser.add_argument("--memory", action="store_true", help="keep the SQLite corpus in RAM instead of a temp file (needs ~5 KB of RAM per chunk)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--postgres-note", action="store_true", help="print how to measure the pgvector/HNSW path")
    args = parser.parse_args()
    if args.postgres_note:
        print("pgvector/HNSW path: run EXPLAIN (ANALYZE, BUFFERS) on the `<=>` ORDER BY ... LIMIT query generated by "
              "retrieval_pipeline._pgvector_rank_chunks against a Postgres with the vector extension and the "
              "ix_document_chunks_embedding_vector_hnsw index; this script does not touch any real database.")
        return 0
    report = asyncio.run(main_async(args))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_table(report)
    return 0 if all(r.get("errors", 0) == 0 for c in report["corpora"] for r in c.get("runs", [])) else 1


if __name__ == "__main__":
    raise SystemExit(main())
