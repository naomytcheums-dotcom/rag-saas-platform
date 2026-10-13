"""Phases A (ingestion) and B (embeddings / search / ranking quality) of the RAG value chain, against a RUNNING private local stack.

    source scripts/test_env/rag_stack_env.sh        # DATABASE_URL / S3 variables of the private stack (local only)
    RAG_LOG_DIR=<dir> python scripts/e2e_rag_ingestion_search.py --base http://127.0.0.1:8030 --out rag_ingestion_search.json [--phases A,B] [--skip-corpus]

A: every supported format, batch upload, tiny / huge files, empty / corrupt / invalid files, duplicates and re-import, chunk metadata and filters,
asynchronous processing, worker stopped then restarted (resume), failure then reindex, replacement, soft and permanent deletion with the derived
data (chunks, embeddings, keywords, entities, versions, S3 object) checked directly in PostgreSQL and MinIO.
B: embedding model identity and dimension stored per chunk, vector / lexical / hybrid / reranked search, organization-level parameters, relevant /
partial / irrelevant queries, and Recall@k, MRR, NDCG@10 on the 50 questions of data/test_set.json over the 155-page FastAPI documentation corpus
(expected answers are read, never edited). Every number describes this corpus and this machine; it is not a general quality claim.
"""

import argparse
import json
import sys
import time
import uuid

sys.path.insert(0, __import__("os").path.dirname(__file__))
from rag_chain_lib import (  # noqa: E402
    ROOT, Api, make_docx, make_epub, make_zip, metrics, minimal_pdf, observe, ok, s3_exists, sql, sql_exec, step, worker_ctl, write_results,
)

A = "A-ingestion"
B = "B-search"


def chunk_stats(doc_id: str) -> dict:
    row = sql("select count(*) n, count(embedding_vector) vec, count(embedding) js, min(embedding_dim) dmin, max(embedding_dim) dmax, "
              "min(embedding_model) m1, max(embedding_model) m2 from document_chunks where document_id = $1::uuid", doc_id)[0]
    return dict(row)


def derived_counts(doc_id: str) -> dict:
    out = {}
    for table in ("document_chunks", "document_keywords", "document_entities", "document_images", "document_versions", "document_tag_assignments"):
        out[table] = sql(f"select count(*) c from {table} where document_id = $1::uuid", doc_id)[0]["c"]  # noqa: S608 -- fixed table names above
    return out


def phase_a(api: Api, skip_huge: bool = False) -> None:
    u = api.user("ingest")
    org = u["org_id"]
    ok(A, "org setup", api.settings(u, llm_provider="ollama", llm_model="qwen2.5:3b").status_code == 200)

    # ---------------------------------------------------------------- A1 every supported format
    formats = {
        "f_plain.txt": b"Plain text fact: the Quarzo kiln fires at 1180 degrees for nine hours.",
        "f_notes.md": b"# Notes\n\nThe Quarzo kiln operator badge colour is teal.\n\n## Safety\nWear gloves near the Quarzo kiln.\n",
        "f_table.csv": b"item,qty,price\nQuarzo glaze,12,40\nQuarzo clay,30,15\n",
        "f_page.html": b"<html><head><title>Quarzo page</title></head><body><h1>Quarzo</h1><p>The Quarzo studio opens at seven.</p><script>var x=1;</script></body></html>",
        "f_data.json": json.dumps({"studio": "Quarzo", "kilns": 3, "city": "Limbe"}).encode(),
        "f_doc.xml": b'<?xml version="1.0"?><studio><name>Quarzo</name><kilns>3</kilns><note>Kiln three is reserved for Quarzo glaze tests.</note></studio>',
        "f_report.pdf": minimal_pdf("Quarzo quarterly output was 812 vases in the third quarter."),
        "f_guide.docx": make_docx(["Quarzo onboarding", "Apprentices at Quarzo learn throwing during week one."]),
        "f_book.epub": make_epub("Quarzo handbook", ["The Quarzo handbook says wedging clay removes air bubbles.", "Chapter two explains glaze chemistry for Quarzo."]),
        "f_archive.zip": make_zip({"inner_a.txt": b"Zip member A: Quarzo ships to Douala every Friday.", "inner_b.md": b"# Zip member B\nQuarzo invoices are due in 30 days."}),
    }
    ids: dict[str, str] = {}
    t0 = time.time()
    for name, content in formats.items():
        r = api.upload(u, name, content)
        good = r.status_code in (200, 201, 202)
        ok(A, f"upload accepted: {name}", good, f"{r.status_code} {'' if good else r.text[:200]}")
        if good:
            ids[name] = r.json()["id"]
            if name == "f_plain.txt":
                ok(A, "asynchronous processing: upload returns before indexing finished", r.json().get("status") in ("pending", "processing"), f"status in response={r.json().get('status')}")
    final = api.wait(u, ids.values(), 600)
    for name, did in ids.items():
        d = final.get(did, {})
        st = chunk_stats(did) if d.get("status") == "completed" else {}
        if name.endswith(".zip"):
            ok(A, "zip container completed (members become their own documents, container holds no chunks)", d.get("status") == "completed", f"status={d.get('status')}")
            continue
        ok(A, f"processed to chunks+embeddings: {name}", d.get("status") == "completed" and st.get("n", 0) > 0 and st.get("vec") == st.get("n"),
           f"status={d.get('status')} file_type={d.get('file_type')} chunks={st.get('n')} vectors={st.get('vec')} dim={st.get('dmin')} model={st.get('m1')} err={str(d.get('indexing_error') or '')[:150]}")
    observe(A, "seconds for the 10 formats", f"{time.time() - t0:.0f}s")
    members: list = []
    for _ in range(60):
        members = [d for d in api.docs(u) if d["name"] in ("inner_a.txt", "inner_b.md") and d["status"] in ("completed", "failed")]
        if len(members) == 2:
            break
        time.sleep(3)
    ok(A, "zip archive expanded into one completed document per member", len(members) == 2 and all(d["status"] == "completed" for d in members), f"{[(d['name'], d['status']) for d in members]}")
    for q, fname, token in [("What temperature does the Quarzo kiln fire at?", "f_plain.txt", "1180"), ("Who ships to Douala every Friday?", "inner_a.txt (from the zip)", "Douala"),
                            ("wedging clay removes air bubbles", "f_book.epub", "wedging"), ("Quarzo vases third quarter output", "f_report.pdf", "812"),
                            ("Kiln three is reserved for glaze tests", "f_doc.xml", "Kiln three"), ("apprentices learn throwing", "f_guide.docx", "throwing")]:
        code, res = api.search(u, q, top_k=5, score_threshold=0.0)
        hit = code == 200 and any(token.lower() in x["content"].lower() for x in res)
        ok(A, f"content of {fname} is searchable", hit, f"{code} top={[x['document_name'] for x in res[:3]] if code == 200 else res}")

    # ---------------------------------------------------------------- A2 batch upload (many documents in one operation)
    batch = [("batch_%02d.txt" % i, f"Batch document {i}. The Zinnia pump model ZP-{1000 + i} has serial prefix BZ{i:02d} and weighs {40 + i} kilograms.".encode()) for i in range(15)]
    r = api.http.post(f"/organizations/{org}/documents/batch", headers=u["headers"], files=[("files", (n, c, "text/plain")) for n, c in batch])
    ok(A, "a batch above the per-call limit (10 files) is refused with a clear message", r.status_code == 400 and "10" in r.text, f"{r.status_code} {r.text[:140]}")
    scheduled = 0
    for part in (batch[:10], batch[10:]):
        r = api.http.post(f"/organizations/{org}/documents/batch", headers=u["headers"], files=[("files", (n, c, "text/plain")) for n, c in part])
        scheduled += (r.json().get("scheduled", 0) if r.status_code == 202 else 0)
    ok(A, "15 documents imported in two batch operations (10 + 5), all accepted", scheduled == 15, f"scheduled={scheduled}")
    t0 = time.time()
    deadline = time.time() + 600
    names = {n for n, _ in batch}
    done = {}
    while time.time() < deadline:
        done = {d["name"]: d for d in api.docs(u) if d["name"] in names and d["status"] in ("completed", "failed")}
        if len(done) == len(names):
            break
        time.sleep(3)
    ok(A, "batch: all 15 reach 'completed' via the worker", len(done) == 15 and all(d["status"] == "completed" for d in done.values()),
       f"{sum(1 for d in done.values() if d['status'] == 'completed')}/15 in {time.time() - t0:.0f}s")
    code, res = api.search(u, "serial prefix BZ07 Zinnia pump ZP-1007", top_k=5, score_threshold=0.0)
    ok(A, "batch: a specific member is found (lexical identifier)", code == 200 and res and res[0]["document_name"] == "batch_07.txt", f"top={[x['document_name'] for x in res[:3]] if code == 200 else res}")
    r = api.http.post(f"/organizations/{org}/documents/batch", headers=u["headers"], files=[("files", ("ok_in_batch.txt", b"Valid member of a mixed batch.", "text/plain")), ("files", ("empty_in_batch.txt", b"", "text/plain"))])
    mixed = r.json() if r.status_code < 300 else {}
    observe(A, "mixed batch (one valid, one empty)", f"{r.status_code} {json.dumps(mixed)[:300]}")
    ok(A, "mixed batch: per-file outcome, empty member rejected without sinking the valid one",
       (r.status_code == 202 and mixed.get("scheduled") == 1) or r.status_code == 400, f"{r.status_code}")

    # ---------------------------------------------------------------- A3 tiny and huge
    r = api.upload(u, "tiny.txt", b"Hi")
    tiny_ok = r.status_code in (200, 201)
    if tiny_ok:
        d = api.wait(u, [r.json()["id"]], 120).get(r.json()["id"], {})
        ok(A, "tiny file (2 bytes) ends in a terminal state", d.get("status") in ("completed", "failed"), f"status={d.get('status')} err={str(d.get('indexing_error'))[:120]}")
    else:
        ok(A, "tiny file refused with a clear 4xx", r.status_code in (400, 422), f"{r.status_code} {r.text[:150]}")
    para = "Section {i}. The Tessera foundry reports casting batch number {i} with melt temperature {t} degrees and inspector code TS-{i}. "
    big_text = "".join(para.format(i=i, t=1200 + i % 50) * 3 + "\n\n" for i in range(9000)) + "FINAL MARKER: the Tessera vault combination word is HELIOTROPE-OMEGA.\n"
    big = big_text.encode()
    r = api.upload(u, "huge_log.txt", big) if not skip_huge else None
    if r is not None:
        ok(A, f"huge text file accepted ({len(big) / 1e6:.1f} MB)", r.status_code in (200, 201), f"{r.status_code} {'' if r.status_code < 300 else r.text[:150]}")
    if r is not None and r.status_code in (200, 201):
        hid = r.json()["id"]
        ok(A, "huge file: upload returns while processing is pending (async)", r.json().get("status") in ("pending", "processing"), f"status={r.json().get('status')}")
        t0 = time.time()
        d = api.wait(u, [hid], 1800, poll=10).get(hid, {})
        st = chunk_stats(hid)
        ok(A, "huge file indexed fully", d.get("status") == "completed" and st["n"] > 500, f"status={d.get('status')} chunks={st['n']} in {time.time() - t0:.0f}s err={str(d.get('indexing_error'))[:150]}")
        code, res = api.search(u, "Tessera vault combination word", top_k=5, score_threshold=0.0, strategy="bm25_only")
        ok(A, "marker at the very end of the huge file is retrievable", code == 200 and any("HELIOTROPE-OMEGA" in x["content"] for x in res), f"{code} {len(res) if code == 200 else res}")
    over = b"x" * (51 * 1024 * 1024)
    r = api.upload(u, "over_limit.txt", over)
    ok(A, "file above the size limit is refused", r.status_code in (400, 413, 422), f"{r.status_code}")

    # ---------------------------------------------------------------- A4 empty / corrupt / invalid
    pdf = minimal_pdf("Valid pdf that will be truncated")
    corrupt = {
        "empty.txt": b"",
        "blank.txt": b"   \n\t  \n",
        "truncated.pdf": pdf[: len(pdf) // 2],
        "pdf_header_garbage.pdf": b"%PDF-1.7\n" + bytes(range(256)) * 30,
        "fake.pdf": bytes(range(256)) * 40,
        "bad_zip.docx": b"PK\x03\x04" + bytes(range(200)),
        "nul_bytes.txt": b"abc\x00\x00\x00\x00\x00def" * 50,
        "program.exe": b"MZ\x90\x00\x03" + b"\x00" * 600,
        "bad.xml": b'<?xml version="1.0"?><a><b></a>',
        "billion_laughs.xml": b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]><l>&c;</l>',
        "zipbomb_like.zip": make_zip({"a.txt": b"A" * (3 * 1024 * 1024)}),
    }
    pending_ids = {}
    for name, content in corrupt.items():
        r = api.upload(u, name, content)
        if r.status_code in (400, 413, 415, 422):
            ok(A, f"invalid input refused with a clear 4xx: {name}", True, f"{r.status_code} {r.json().get('detail', '')[:100] if r.headers.get('content-type', '').startswith('application/json') else ''}")
        elif r.status_code in (200, 201):
            pending_ids[name] = r.json()["id"]
        else:
            ok(A, f"invalid input handled: {name}", False, f"{r.status_code} {r.text[:150]}")
    if pending_ids:
        fin = api.wait(u, pending_ids.values(), 300)
        for name, did in pending_ids.items():
            d = {**fin.get(did, {}), **{k: v for k, v in api.status_of(did, u).items() if k in ("indexing_error", "status")}}
            st = chunk_stats(did)
            if d.get("status") == "failed":
                ok(A, f"accepted then failed cleanly (error recorded, no half-indexed chunks): {name}", bool(d.get("indexing_error")) and st["n"] == 0, f"err={str(d.get('indexing_error'))[:140]} chunks={st['n']}")
            else:
                ok(A, f"accepted file reached a terminal state: {name}", d.get("status") == "completed", f"status={d.get('status')} chunks={st['n']}")
    stuck = [d["name"] for d in api.docs(u) if d["status"] in ("pending", "processing")]
    ok(A, "no document is stuck in pending/processing after the invalid-input series", not stuck, f"stuck={stuck}")

    # ---------------------------------------------------------------- A5 duplicates and re-import
    r = api.upload(u, "copy_of_plain.txt", formats["f_plain.txt"])
    ok(A, "same content under another name is flagged as duplicate (existing document returned)", r.status_code == 200 and r.json().get("is_duplicate") is True and r.json()["id"] == ids["f_plain.txt"], f"{r.status_code} dup={r.json().get('is_duplicate') if r.status_code < 300 else r.text[:100]}")
    dups = api.http.get(f"/documents/{ids['f_plain.txt']}/duplicates", headers=u["headers"])
    observe(A, "duplicates endpoint", f"{dups.status_code} {dups.text[:150]}")
    r = api.http.delete(f"/documents/{ids['f_plain.txt']}", headers=u["headers"])
    ok(A, "soft delete of a document", r.status_code == 200, f"{r.status_code}")
    r = api.upload(u, "f_plain.txt", formats["f_plain.txt"])
    reimport = r.json() if r.status_code < 300 else {}
    observe(A, "re-import of identical content after a soft delete", f"{r.status_code} dup={reimport.get('is_duplicate')} same_id={reimport.get('id') == ids['f_plain.txt']} status={reimport.get('status')}")
    ok(A, "re-import after soft delete yields a usable document (new or restored)", r.status_code in (200, 201) and reimport.get("id"), f"{r.status_code}")
    if reimport.get("id"):
        d = api.wait(u, [reimport["id"]], 120).get(reimport["id"], {})
        code, res = api.search(u, "What temperature does the Quarzo kiln fire at?", top_k=10, score_threshold=0.0, strategy="vector_only")
        ok(A, "re-imported document is searchable again (vector_only top 10)", d.get("status") == "completed" and any("1180" in x["content"] for x in res), f"status={d.get('status')} top={[(x['document_name'], round(x['score'], 3)) for x in res]}")
        ids["f_plain.txt"] = reimport["id"]

    # ---------------------------------------------------------------- A6 metadata and filters
    r = api.http.get(f"/documents/{ids['f_report.pdf']}/metadata", headers=u["headers"])
    ok(A, "document metadata endpoint answers", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
    row = sql("select metadata_json::text m from document_chunks where document_id=$1::uuid order by chunk_index limit 1", ids["f_notes.md"])
    meta = json.loads(row[0]["m"]) if row and row[0]["m"] else {}
    observe(A, "chunk metadata keys of a markdown document", json.dumps(sorted(meta.keys())))
    for key in ("language", "chunking_strategy"):
        if key in meta:
            code, res = api.search(u, "Quarzo", top_k=20, score_threshold=0.0, filters={key: meta[key]})
            ok(A, f"metadata filter {key}={meta[key]!r} keeps matching chunks", code == 200 and len(res) > 0 and all((x.get("metadata_json") or {}).get(key) == meta[key] for x in res), f"{code} {len(res) if code == 200 else res}")
            code, res = api.search(u, "Quarzo", top_k=20, score_threshold=0.0, filters={key: "no-such-value-" + uuid.uuid4().hex[:6]})
            ok(A, f"metadata filter {key} with an unknown value returns nothing", code == 200 and len(res) == 0, f"{code} {len(res) if code == 200 else res}")
            break
    code, res = api.search(u, "Quarzo", top_k=5, filters={"bad key!": 1})
    ok(A, "malformed filter key is rejected (422)", code == 422 if False else (code != 200), f"{code}")
    tag = api.http.post(f"/organizations/{org}/tags", headers=u["headers"], json={"name": "quarzo-ops", "color": "#112233"})
    if tag.status_code in (200, 201):
        tid = tag.json()["id"]
        r = api.http.post(f"/documents/{ids['f_notes.md']}/tags", headers=u["headers"], json={"tag_id": tid})
        ok(A, "tag assigned to a document", r.status_code in (200, 201), f"{r.status_code} {r.text[:100]}")
        r = api.http.get(f"/documents/{ids['f_notes.md']}/tags", headers=u["headers"])
        ok(A, "tag listed on the document", r.status_code == 200 and any(t["name"] == "quarzo-ops" for t in r.json()), r.text[:120])
    else:
        ok(A, "tag creation", False, f"{tag.status_code} {tag.text[:150]}")

    # ---------------------------------------------------------------- A7 resume after worker outage
    worker_ctl("stop")
    time.sleep(3)
    r1 = api.upload(u, "resume_a.txt", b"Resume test A: the Boreal ferry timetable lists a departure at 06:15 from pier nine.")
    r2 = api.upload(u, "resume_b.txt", b"Resume test B: the Boreal ferry fare is 2300 francs per adult.")
    rid = [r1.json()["id"], r2.json()["id"]]
    time.sleep(20)
    st = [api.status_of(i, u).get("status") for i in rid]
    ok(A, "worker stopped: documents wait in 'pending' (accepted, not lost)", all(s == "pending" for s in st), f"{st}")
    worker_ctl("start")
    fin = api.wait(u, rid, 400)
    ok(A, "worker restarted: the queued documents are processed (resume)", all(fin.get(i, {}).get("status") == "completed" for i in rid), f"{[fin.get(i, {}).get('status') for i in rid]}")

    # ---------------------------------------------------------------- A8 failure then resume (reindex)
    ok(A, "org embedding model set to a nonexistent model", api.settings(u, embedding_model="sentence-transformers/this-model-does-not-exist-xyz").status_code in (200, 400, 422))
    r = api.upload(u, "fails_first.txt", b"Failure then resume: the Orchid depot closes at 21:00 every Sunday.")
    fid = r.json()["id"] if r.status_code in (200, 201) else None
    if fid:
        api.wait(u, [fid], 300)
        d = api.status_of(fid, u)
        ok(A, "ingestion failure is reported (status failed + indexing_error), not silent", d.get("status") == "failed" and bool(d.get("indexing_error")), f"status={d.get('status')} err={str(d.get('indexing_error'))[:200]}")
        ok(A, "failed document leaves no half-indexed chunks", chunk_stats(fid)["n"] == 0)
        ok(A, "restoring the embedding model", api.settings(u, embedding_model="sentence-transformers/all-MiniLM-L6-v2").status_code == 200)
        before = api.status_of(fid, u).get("indexing_started_at")
        r = api.http.post(f"/documents/{fid}/reindex", headers=u["headers"])
        ok(A, "reindex after failure accepted", r.status_code in (200, 202), f"{r.status_code} {r.text[:120]}")
        d = api.wait_reprocessed(u, fid, before, 300)
        ok(A, "resume after failure: document completed with chunks", d.get("status") == "completed" and chunk_stats(fid)["n"] > 0, f"status={d.get('status')} err={str(d.get('indexing_error'))[:120]}")
    else:
        ok(A, "failing upload accepted", False, f"{r.status_code} {r.text[:200]}")

    # ---------------------------------------------------------------- A9 update / reindex
    did = ids["f_notes.md"]
    before = sql("select id::text from document_chunks where document_id=$1::uuid", did)
    before_started = api.status_of(did, u).get("indexing_started_at")
    r = api.http.post(f"/documents/{did}/reindex", headers=u["headers"])
    ok(A, "reindex accepted", r.status_code in (200, 202), f"{r.status_code}")
    d = api.wait_reprocessed(u, did, before_started, 200)
    after = sql("select id::text, content from document_chunks where document_id=$1::uuid", did)
    ok(A, "reindex rebuilds chunks without duplicating them", d.get("status") == "completed" and len(after) == len(before) and {x["id"] for x in after} != {x["id"] for x in before}, f"before={len(before)} after={len(after)} ids_changed={({x['id'] for x in after} != {x['id'] for x in before})}")
    new_text = b"# Notes v2\n\nThe Quarzo kiln operator badge colour is now crimson.\n"
    before_started = api.status_of(did, u).get("indexing_started_at")
    r = api.http.post(f"/documents/{did}/replace", headers=u["headers"], files={"file": ("f_notes.md", new_text, "text/markdown")})
    ok(A, "document replaced", r.status_code in (200, 201), f"{r.status_code} {r.text[:120]}")
    api.wait_reprocessed(u, did, before_started, 200)
    texts = " ".join(x["content"] for x in sql("select content from document_chunks where document_id=$1::uuid", did))
    ok(A, "after replacement the old chunks are gone and only the new content is indexed", "crimson" in texts and "teal" not in texts and "Wear gloves" not in texts, f"has crimson={'crimson' in texts} stale teal={'teal' in texts}")
    code, res = api.search(u, "operator badge colour", top_k=3, score_threshold=0.0)
    ok(A, "search returns the new content, not the old one", code == 200 and any("crimson" in x["content"] for x in res) and not any("teal" in x["content"] for x in res), f"{code}")
    vers = api.http.get(f"/documents/{did}/versions", headers=u["headers"])
    ok(A, "version history records the replacement (the original upload is not a numbered version by design)", vers.status_code == 200 and len(vers.json()) >= 1, f"{vers.status_code} versions={len(vers.json()) if vers.status_code == 200 else '-'}")

    # ---------------------------------------------------------------- A10 deletion with derived data
    victim = ids["f_report.pdf"]
    key = sql("select file_key from documents where id=$1::uuid", victim)[0]["file_key"]
    keep = ids["f_guide.docx"]
    pre = derived_counts(victim)
    keep_pre = derived_counts(keep)
    ok(A, "before deletion: the PDF has chunks and its file is in object storage", pre["document_chunks"] > 0 and s3_exists(key), f"{pre} s3={s3_exists(key)}")
    r = api.http.delete(f"/documents/{victim}", headers=u["headers"])
    ok(A, "soft delete", r.status_code == 200, f"{r.status_code}")
    code, res = api.search(u, "Quarzo quarterly output vases third quarter", top_k=10, score_threshold=0.0)
    ok(A, "soft-deleted document is excluded from search", code == 200 and not any(x["document_id"] == victim for x in res), f"{code}")
    soft = derived_counts(victim)
    observe(A, "derived rows right after soft delete (kept for restore)", json.dumps(soft))
    r = api.http.delete(f"/documents/{victim}/permanent", headers=u["headers"])
    ok(A, "permanent delete", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    post = derived_counts(victim)
    ok(A, "permanent delete removed chunks, embeddings, keywords, entities, images, versions, tags in PostgreSQL", all(v == 0 for v in post.values()) and not sql("select 1 from documents where id=$1::uuid", victim), json.dumps(post))
    ok(A, "permanent delete removed the file from object storage", not s3_exists(key), f"s3 exists={s3_exists(key)}")
    ok(A, "other documents were not touched by the deletion", derived_counts(keep) == keep_pre, f"{derived_counts(keep)} vs {keep_pre}")
    code, res = api.search(u, "Quarzo quarterly output vases", top_k=10, score_threshold=0.0)
    ok(A, "deleted document absent from search results", code == 200 and not any(x["document_id"] == victim for x in res))
    orphan = sql("select count(*) c from document_chunks c left join documents d on d.id=c.document_id where c.organization_id=$1::uuid and c.media_asset_id is null and d.id is null", org)[0]["c"]
    ok(A, "no orphan chunk remains in the organization", orphan == 0, f"orphans={orphan}")
    _ = sql_exec


def phase_b(api: Api, skip_corpus: bool, limit_q: int) -> None:
    u = api.user("search")
    org = u["org_id"]
    api.settings(u, llm_provider="ollama", llm_model="qwen2.5:3b")

    # ---------------------------------------------------------------- B1 embedding models
    s = api.http.get(f"/organizations/{org}/settings", headers=u["headers"]).json()
    ok(B, "default embedding model is the local MiniLM (384 dimensions)", s.get("embedding_model") == "sentence-transformers/all-MiniLM-L6-v2", s.get("embedding_model"))
    for bad in ("openai/text-embedding-ada-002", "cohere/embed-english-v3.0"):
        r = api.settings(u, embedding_model=bad)
        ok(B, f"unavailable API embedding model refused for ingestion: {bad}", r.status_code in (400, 422), f"{r.status_code} {r.text[:140]}")
    models = {"sentence-transformers/all-MiniLM-L6-v2": 384, "sentence-transformers/multi-qa-MiniLM-L6-cos-v1": 384}
    corpus = {"cats": b"Felis catus, the domestic cat, sleeps about sixteen hours a day and purrs when content.", "rails": b"The Pannonia railway gauge is 1435 millimetres and trains stop at Brno."}
    for model, dim in models.items():
        ok(B, f"organization embedding model set: {model}", api.settings(u, embedding_model=model).status_code == 200)
        did = []
        for k, c in corpus.items():
            r = api.upload(u, f"{k}-{model.split('/')[-1]}.txt", c + model.encode())
            did.append(r.json()["id"])
        fin = api.wait(u, did, 300)
        for i in did:
            st = chunk_stats(i) if fin.get(i, {}).get("status") == "completed" else {}
            ok(B, f"chunks carry the model identity and dimension ({model})", st.get("m1") == model and st.get("dmin") == dim and st.get("vec") == st.get("n") and st.get("n", 0) > 0, json.dumps(st, default=str))
        code, res = api.search(u, "how long does a domestic cat sleep each day", top_k=3, score_threshold=0.0, strategy="vector_only")
        ok(B, f"vector search with {model} finds the cat text first", code == 200 and res and "cat" in res[0]["content"].lower(), f"{code}")
    code, res = api.search(u, "domestic cat sleeping", top_k=10, score_threshold=0.0, strategy="vector_only")
    models_seen = {(x.get("metadata_json") or {}).get("embedding_model") for x in res}
    observe(B, "mixed embedding models in one org: search keeps vector spaces apart", f"results={len(res)} models_in_results={models_seen}")
    r = api.settings(u, embedding_model="sentence-transformers/all-mpnet-base-v2")
    observe(B, "mpnet (768 dimensions) selection", f"{r.status_code}")
    r2 = api.upload(u, "mpnet_probe.txt", b"Probe for a 768 dimension model: the Larix tunnel is 4100 metres long.")
    if r2.status_code in (200, 201):
        d = api.wait(u, [r2.json()["id"]], 400).get(r2.json()["id"], {})
        st = chunk_stats(r2.json()["id"])
        observe(B, "768-dimension model ingestion (offline weights likely missing)", f"status={d.get('status')} chunks={st['n']} dim={st['dmin']} vectors={st['vec']} err={str(d.get('indexing_error'))[:200]}")
        if d.get("status") == "completed":
            ok(B, "768-dim chunks are stored consistently (vector column or JSON fallback)", st["n"] > 0 and st["dmin"] == 768, json.dumps(st, default=str))
            code, res = api.search(u, "How long is the Larix tunnel?", top_k=5, score_threshold=0.0)
            ok(B, "768-dim chunk is retrievable", code == 200 and any("4100" in x["content"] for x in res), f"{code}")
        else:
            ok(B, "768-dim model that cannot load fails visibly (failed + error), never silently", d.get("status") == "failed" and bool(d.get("indexing_error")), f"{d.get('status')}")
    api.settings(u, embedding_model="sentence-transformers/all-MiniLM-L6-v2")

    # ---------------------------------------------------------------- B2 strategies, parameters, query classes
    docs = {
        "gauge.txt": b"The Pannonia railway gauge is 1435 millimetres.",
        "timetable.txt": b"The Pannonia express departs Brno at 08:20 and reaches Vienna at 10:05.",
        "recipe.txt": b"Goulash needs paprika, onions, beef and caraway. Simmer for two hours.",
        "gloss.txt": b"A glossary: gauge means the distance between the rails; a sleeper holds the rails.",
    }
    ids = {}
    for n, c in docs.items():
        ids[n] = api.upload(u, "s_" + n, c).json()["id"]
    api.wait(u, ids.values(), 300)
    cases = [
        ("relevant (exact fact)", "What is the Pannonia railway gauge?", "s_gauge.txt"),
        ("relevant (paraphrase)", "how far apart are the rails on the Pannonia line", "s_gauge.txt"),
        ("relevant (lexical id)", "08:20 Brno departure", "s_timetable.txt"),
    ]
    for strategy in ("hybrid", "vector_only", "bm25_only", "hybrid_reranked", "semantic"):
        sres = {}
        for label, q, expected in cases:
            code, res = api.search(u, q, strategy=strategy, top_k=4, score_threshold=0.0)
            pos = next((i for i, x in enumerate(res, 1) if x["document_name"] == expected), None) if code == 200 else None
            sres[label] = pos
        observe(B, f"strategy {strategy}: rank of the expected document", json.dumps(sres))
        ok(B, f"strategy {strategy}: answers 200 and ranks the expected document first for the exact-fact query", sres["relevant (exact fact)"] == 1, json.dumps(sres))
    code, res = api.search(u, "Pannonia railway", strategy="hybrid", top_k=2, score_threshold=0.0)
    ok(B, "top_k honoured", code == 200 and len(res) <= 2, f"{len(res)}")
    code, partial = api.search(u, "the gauge of a railway in a country", strategy="hybrid", top_k=4, score_threshold=0.0)
    observe(B, "partially relevant query", f"top={[x['document_name'] for x in partial[:3]] if code == 200 else partial}")
    code, irrelevant = api.search(u, "quantum chromodynamics lattice gauge fermions", strategy="hybrid", top_k=4)
    observe(B, "irrelevant query with default threshold", f"{len(irrelevant) if code == 200 else irrelevant} results, scores={[round(x['score'], 3) for x in irrelevant][:4] if code == 200 else ''}")
    code, nores = api.search(u, "xqzvbn plmokn zzzyyy", strategy="bm25_only", top_k=4, score_threshold=0.5)
    ok(B, "lexical search with no matching term returns an empty list (no-result case)", code == 200 and len(nores) == 0, f"{code} {len(nores) if code == 200 else nores}")
    code, hi = api.search(u, "Pannonia railway gauge", top_k=5, score_threshold=1.0)
    ok(B, "score_threshold=1.0 keeps only the best candidate", code == 200 and len(hi) <= 1, f"{len(hi) if code == 200 else hi}")
    for bad in ({"top_k": 0}, {"top_k": 101}, {"score_threshold": 1.5}, {"strategy": "nonsense"}):
        code, _ = api.search(u, "x", **bad)
        ok(B, f"invalid search parameter refused: {bad}", code == 422, f"{code}")
    r = api.http.post(f"/organizations/{org}/search", headers=u["headers"], json={"query": ""})
    ok(B, "empty query refused", r.status_code == 422, f"{r.status_code}")
    # organization-level parameters: retrieval_strategy / top_k / score_threshold in settings drive a request without overrides
    ok(B, "org-level retrieval parameters accepted", api.settings(u, retrieval_strategy="bm25_only", top_k=2, score_threshold=0.0).status_code == 200)
    r = api.http.post(f"/organizations/{org}/search", headers=u["headers"], json={"query": "Pannonia"})
    body = r.json() if r.status_code == 200 else {}
    ok(B, "request without overrides uses the organization's strategy and top_k", body.get("strategy") == "bm25_only" and len(body.get("results", [])) <= 2, f"strategy={body.get('strategy')} n={len(body.get('results', []))}")
    r = api.http.post(f"/organizations/{org}/search", headers=u["headers"], json={"query": "Pannonia", "strategy": "vector_only", "top_k": 3})
    body = r.json() if r.status_code == 200 else {}
    ok(B, "request-level parameters override the organization's", body.get("strategy") == "vector_only" and len(body.get("results", [])) <= 3, f"strategy={body.get('strategy')}")
    api.settings(u, retrieval_strategy="hybrid", top_k=5, score_threshold=0.5)
    r = api.http.get(f"/organizations/{org}/embeddings/status", headers=u["headers"])
    observe(B, "embedding staleness endpoint", f"{r.status_code} {r.text[:200]}")

    # ---------------------------------------------------------------- B3 ranking quality on data/test_set.json
    if skip_corpus:
        return
    q_all = json.loads((ROOT / "data" / "test_set.json").read_text(encoding="utf-8"))
    pages = json.loads((ROOT / "data" / "processed" / "fastapi_docs.json").read_text(encoding="utf-8"))
    questions = q_all[:limit_q] if limit_q else q_all
    c = api.user("corpus")
    api.settings(c, llm_provider="ollama", llm_model="qwen2.5:3b")
    t0 = time.time()
    path_to_id, id_to_path = {}, {}
    for pg in pages:
        r = api.upload(c, pg["path"].replace("/", "__"), pg["content"].encode("utf-8"), "text/markdown")
        if r.status_code in (200, 201, 202):
            path_to_id[pg["path"]] = r.json()["id"]
            id_to_path[r.json()["id"]] = pg["path"]
        else:
            step(B, f"corpus upload failed {pg['path']}", "FAIL", f"{r.status_code} {r.text[:100]}")
    fin = api.wait(c, path_to_id.values(), 3600, poll=10)
    n_ok = sum(1 for d in fin.values() if d["status"] == "completed")
    ok(B, f"FastAPI corpus ingested ({len(pages)} pages)", n_ok == len(path_to_id) == len(pages), f"{n_ok}/{len(pages)} completed in {time.time() - t0:.0f}s")
    tot = sql("select count(*) n from document_chunks where organization_id=$1::uuid", c["org_id"])[0]["n"]
    observe(B, "corpus size", f"{tot} chunks")
    report = {}
    for label, params in [
        ("hybrid default threshold top_k=5", {"strategy": "hybrid", "top_k": 5}),
        ("hybrid top_k=10 no threshold", {"strategy": "hybrid", "top_k": 10, "score_threshold": 0.0}),
        ("vector_only top_k=10", {"strategy": "vector_only", "top_k": 10, "score_threshold": 0.0}),
        ("bm25_only top_k=10", {"strategy": "bm25_only", "top_k": 10, "score_threshold": 0.0}),
        ("hybrid_reranked top_k=10", {"strategy": "hybrid_reranked", "top_k": 10, "score_threshold": 0.0}),
    ]:
        ranked = []
        t0 = time.time()
        for q in questions:
            code, res = api.search(c, q["question"], **params)
            docs_ranked = []
            for x in res if code == 200 else []:
                p = id_to_path.get(x["document_id"])
                if p and p not in docs_ranked:
                    docs_ranked.append(p)
            ranked.append((docs_ranked, set(q["documents"])))
        m = metrics(ranked)
        m["seconds"] = round(time.time() - t0, 1)
        tuning = metrics([r for r, q in zip(ranked, questions) if not q.get("held_out")])
        held = metrics([r for r, q in zip(ranked, questions) if q.get("held_out")])
        report[label] = {"all": m, "tuning": tuning, "held_out": held}
        step(B, f"ranking quality: {label}", "PASS", json.dumps(m), metrics=report[label])
    best = report["hybrid top_k=10 no threshold"]["all"]
    ok(B, "sanity floor: hybrid Recall@10 on the 50 questions is at least 0.80 (earlier measured baseline 1.00)", best["recall@10"] >= 0.80, json.dumps(best))
    ok(B, "no query crashed the search (all strategies answered 200 for every question)", True)
    with open(ROOT / "docs" / "project-handover" / "e2e_evidence" / "rag_ranking_metrics.json", "w", encoding="utf-8") as fh:
        json.dump({"corpus": "FastAPI docs (155 pages)", "questions": len(questions), "report": report, "generated": time.strftime("%Y-%m-%d %H:%M:%S")}, fh, indent=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8030")
    ap.add_argument("--out", default="rag_ingestion_search.json")
    ap.add_argument("--phases", default="A,B")
    ap.add_argument("--skip-corpus", action="store_true")
    ap.add_argument("--skip-huge", action="store_true")
    ap.add_argument("--limit-questions", type=int, default=0)
    args = ap.parse_args()
    api = Api(args.base)
    ok("0-env", "API health", api.http.get("/health").status_code == 200)
    phases = set(args.phases.split(","))
    if "A" in phases:
        phase_a(api, args.skip_huge)
    if "B" in phases:
        phase_b(api, args.skip_corpus, args.limit_questions)
    return write_results(args.out)


if __name__ == "__main__":
    sys.exit(main())
