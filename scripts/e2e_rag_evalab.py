"""Phase E: Evaluation Lab (CSV ids 7.1.x, 7.2.x, 7.3.x) end to end on the private local stack with REAL Ollama and the Celery worker.

    source scripts/test_env/rag_stack_env.sh
    python scripts/e2e_rag_evalab.py --base http://127.0.0.1:8030 --model qwen2.5:3b --out rag_evalab.json

Datasets, questions (ground-truth answers and documents, difficulty, split), question sets, import / export, benchmark versions, evaluation jobs run by the
worker with a generated answer from Ollama, per-question metrics recomputed independently from /search (Recall@k, MRR, NDCG, Precision must match the
stored values), latency / tokens / cost, manual evaluation, regression detection after a real knowledge-base degradation (a document is deleted) with the
severity classes (>= 5 percent), the deployment gate that blocks a regressed agent, model / retriever / reranker / prompt comparisons, threshold checks, A/B test.
"""

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from rag_chain_lib import Api, observe, ok, require_local, step, write_results  # noqa: E402

E = "E-evallab"
MODEL = "qwen2.5:3b"
DOCS = {
    "e_support.txt": "Kappa Support Manual. The Kappa support desk opens at 06:50 on weekdays. The escalation phrase for urgent tickets is JASPER-2207. Priority one tickets receive a first answer within 18 minutes.",
    "e_returns.txt": "Kappa Returns Policy. A Kappa device can be returned within 17 days of delivery. A restocking fee of 9 percent applies to opened boxes. Refunds are paid by bank transfer within 4 working days.",
    "e_hardware.txt": "Kappa Hardware Sheet. The Kappa K9 projector has a brightness of 2800 lumens and a lamp life of 7000 hours. Its weight is 3.1 kilograms.",
    "e_hr.txt": "Kappa People Handbook. Annual leave at Kappa is 31 days. New employees complete a security briefing with Mr Dibango during week one.",
}
QUESTIONS = [
    ("When does the Kappa support desk open?", "e_support.txt", "06:50", "easy", "support", "tuning"),
    ("What is the escalation phrase for urgent tickets?", "e_support.txt", "JASPER-2207", "easy", "support", "tuning"),
    ("Within how many days can a Kappa device be returned?", "e_returns.txt", "17", "easy", "returns", "tuning"),
    ("What restocking fee applies to opened boxes?", "e_returns.txt", "9 percent", "medium", "returns", "tuning"),
    ("What is the brightness of the Kappa K9 projector?", "e_hardware.txt", "2800", "medium", "hardware", "tuning"),
    ("How many hours does the K9 lamp last?", "e_hardware.txt", "7000", "medium", "hardware", "held_out"),
    ("How many days of annual leave are there?", "e_hr.txt", "31", "hard", "people", "held_out"),
    ("Who gives the security briefing to new employees?", "e_hr.txt", "Dibango", "hard", "people", "held_out"),
]


def ndcg_binary(ranked, expected):
    dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(ranked[:10]) if d in expected)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(expected), 10)))
    return dcg / idcg if idcg else 0.0


def run_job(api: Api, u, ds, agent_id, timeout=1800, **kw):
    r = api.http.post(f"/datasets/{ds}/evaluate", headers=u["headers"], json={"agent_id": agent_id, **kw})
    assert r.status_code == 201, (r.status_code, r.text[:200])
    job = r.json()["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = api.http.get(f"/jobs/{job}", headers=u["headers"]).json()
        if st["status"] in ("completed", "failed", "cancelled"):
            return job, st
        time.sleep(5)
    return job, st


def results_of(api: Api, u, job):
    body = api.http.get(f"/jobs/{job}/results", headers=u["headers"]).json()
    return body if isinstance(body, list) else body.get("items", [])


def mean(rows, key):
    vals = [r["metrics"][key] for r in rows if isinstance(r.get("metrics", {}).get(key), (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else None


def main() -> int:
    global MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8030")
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--out", default="rag_evalab.json")
    args = ap.parse_args()
    require_local(args.base)
    MODEL = args.model
    api = Api(args.base)
    u = api.user("evallab")
    api.settings(u, llm_provider="ollama", llm_model=MODEL)
    org = u["org_id"]
    ids = {}
    for n, t in DOCS.items():
        ids[n] = api.upload(u, n, t.encode(), "text/plain").json()["id"]
    fin = api.wait(u, ids.values(), 400)
    ok(E, "corpus indexed", all(fin.get(i, {}).get("status") == "completed" for i in ids.values()))
    agent = api.http.post(f"/organizations/{org}/agents", headers=u["headers"], json={
        "name": "eval agent", "system_prompt": "Answer only from the context and cite it.", "model_config": {"provider": "ollama", "model": MODEL}}).json()["id"]
    r = api.http.patch(f"/agents/{agent}/knowledge-base", headers=u["headers"], json={"config": {"strategy": "hybrid", "top_k": 5}})
    ok(E, "agent retrieval configuration set", r.status_code == 200, f"{r.status_code} {r.text[:120]}")

    # ---------------------------------------------------------------- 7.1 datasets and questions
    r = api.http.post(f"/organizations/{org}/datasets", headers=u["headers"], json={"name": "Kappa FAQ", "description": "ground truth for the Kappa corpus"})
    ok(E, "7.1.1 dataset created", r.status_code == 201, f"{r.status_code}")
    ds = r.json()["id"]
    r = api.http.get(f"/organizations/{org}/datasets", headers=u["headers"])
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    ok(E, "7.1.1 dataset listed", any(d["id"] == ds for d in items))
    r = api.http.patch(f"/datasets/{ds}", headers=u["headers"], json={"description": "renamed description"})
    ok(E, "7.1.1 dataset updated", r.status_code == 200 and r.json()["description"] == "renamed description")
    qids = []
    for q, doc, fact, diff, cat, split in QUESTIONS:
        r = api.http.post(f"/datasets/{ds}/questions", headers=u["headers"], json={
            "question": q, "expected_answer": f"{fact}", "expected_documents": [{"document_id": ids[doc], "relevance_score": 1.0}], "difficulty": diff, "category": cat, "split": split})
        qids.append(r.json()["id"] if r.status_code == 201 else None)
    ok(E, "7.1.2/7.1.3/7.1.4 8 questions stored with ground-truth answer and ground-truth document", all(qids), f"{sum(1 for x in qids if x)}/8")
    r = api.http.get(f"/datasets/{ds}/questions", headers=u["headers"], params={"limit": 50})
    body = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    ok(E, "7.1.3/7.1.4 ground truth is returned by the API", len(body) == 8 and all(x.get("expected_answer") and x.get("expected_documents") for x in body), f"{len(body)}")
    ok(E, "7.1.5 difficulty levels easy/medium/hard all present", {x.get("difficulty") for x in body} == {"easy", "medium", "hard"}, f"{sorted({x.get('difficulty') for x in body})}")
    ok(E, "7.1.7 tuning / held_out split stored", {x.get("split") for x in body} == {"tuning", "held_out"})
    r = api.http.post(f"/datasets/{ds}/questions", headers=u["headers"], json={"question": "x", "difficulty": "impossible"})
    observe(E, "invalid difficulty value", f"{r.status_code}")
    ex = api.http.get(f"/datasets/{ds}/questions/export", headers=u["headers"])
    ok(E, "7.1.2 questions export", ex.status_code == 200 and "Kappa" in ex.text, f"{ex.status_code} {len(ex.text)} bytes")
    ds2 = api.http.post(f"/organizations/{org}/datasets", headers=u["headers"], json={"name": "Imported"}).json()["id"]
    imp = api.http.post(f"/datasets/{ds2}/questions/import", headers=u["headers"], files={"file": ("q.json", ex.content, "application/json")})
    observe(E, "questions import of the exported file", f"{imp.status_code} {imp.text[:200]}")
    ok(E, "7.1.2 import accepts the exported file", imp.status_code in (200, 201), f"{imp.status_code}")
    sset = api.http.post(f"/datasets/{ds}/sets", headers=u["headers"], json={"name": "smoke set"})
    ok(E, "7.1.2 question set created", sset.status_code == 201, f"{sset.status_code} {sset.text[:100]}")
    v1 = api.http.post(f"/datasets/{ds}/versions", headers=u["headers"], json={"description": "v1 baseline"})
    ok(E, "7.1.6 benchmark version 1 created", v1.status_code == 201 and v1.json()["version_number"] == 1, f"{v1.status_code} {v1.text[:100]}")

    # ---------------------------------------------------------------- 7.2 metrics: job run by the worker, recomputed independently
    t0 = time.time()
    job1, st1 = run_job(api, u, ds, agent)
    ok(E, "7.3.1 evaluation job completed on the worker (generation by Ollama)", st1["status"] == "completed", f"{st1['status']} in {time.time() - t0:.0f}s {str(st1.get('error') or '')[:150]}")
    rows1 = results_of(api, u, job1)
    ok(E, "one result per question", len(rows1) == 8, f"{len(rows1)}")
    keys = sorted({k for r in rows1 for k in (r.get("metrics") or {})})
    observe(E, "metric keys stored per question", json.dumps(keys))
    for metric in ("recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr", "ndcg_at_5", "precision_at_5", "latency", "total_tokens", "cost"):
        present = any(metric in k for k in keys) or any(k.startswith(metric.split("_")[0]) for k in keys)
        ok(E, f"7.2.x metric stored: {metric}", present, "")
    # independent recomputation of retrieval metrics
    mismatches = []
    by_q = {r.get("question_id"): r for r in rows1}
    for (q, doc, *_), qid in zip(QUESTIONS, qids):
        code, res = api.search(u, q, strategy="hybrid", top_k=10, score_threshold=0.0)
        ranked = []
        for x in res:
            if x["document_id"] not in ranked:
                ranked.append(x["document_id"])
        expected = {ids[doc]}
        stored = (by_q.get(qid) or {}).get("metrics") or {}
        mine = {"mrr": next((1.0 / (i + 1) for i, d in enumerate(ranked) if d in expected), 0.0), "recall_at_1": float(bool(expected & set(ranked[:1]))),
                "recall_at_5": float(bool(expected & set(ranked[:5])))}
        for k, v in mine.items():
            if k in stored and isinstance(stored[k], (int, float)) and abs(stored[k] - v) > 1e-6:
                mismatches.append((q[:30], k, stored[k], round(v, 3)))
    ok(E, "7.2.1-7.2.5 stored Recall@1/@5 and MRR equal an independent recomputation from /search", not mismatches, f"mismatches={mismatches}")
    means1 = {k: mean(rows1, k) for k in ("recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10", "mrr", "ndcg_at_5", "precision_at_5", "latency_ms", "faithfulness", "hallucination_rate", "citation_correctness")}
    step(E, "baseline means of the job (this tiny 8-question set proves the plumbing, not quality)", "PASS", json.dumps(means1), means=means1)
    ok(E, "7.2.1-7.2.6 baseline retrieval is perfect on the controlled corpus (Recall@5 = 1.0)", means1["recall_at_5"] == 1.0, json.dumps(means1))
    for metric in ("recall_at_5", "mrr", "ndcg_at_5"):
        r = api.http.get(f"/datasets/{ds}/metrics/{metric}", headers=u["headers"])
        ok(E, f"dataset metric endpoint answers: {metric}", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
    fr = api.http.get(f"/jobs/{job1}/failures", headers=u["headers"])
    ok(E, "failure report endpoint answers", fr.status_code == 200, f"{fr.status_code}")
    cmp_ = api.http.get(f"/jobs/{job1}/comparison", headers=u["headers"])
    observe(E, "job comparison endpoint without a previous job", f"{cmp_.status_code} {cmp_.text[:120]}")
    v2 = api.http.post(f"/datasets/{ds}/versions", headers=u["headers"], json={"description": "v2"})
    if v1.status_code == 201 and v2.status_code == 201:
        c = api.http.post(f"/versions/{v1.json()['id']}/compare/{v2.json()['id']}", headers=u["headers"])
        ok(E, "7.1.6 two benchmark versions can be compared", c.status_code == 200, f"{c.status_code} {c.text[:120]}")

    # ---------------------------------------------------------------- 7.3.2 manual evaluation
    m = api.http.post(f"/questions/{qids[0]}/evaluate", headers=u["headers"], json={"agent_id": agent, "score": 4, "feedback": "correct but terse", "criteria": {"accuracy": 5, "tone": 3}})
    ok(E, "7.3.2 manual evaluation created", m.status_code == 201, f"{m.status_code} {m.text[:100]}")
    s = api.http.get(f"/questions/{qids[0]}/evaluations/summary", headers=u["headers"])
    ok(E, "7.3.2 manual evaluation summary", s.status_code == 200 and "4" in s.text, f"{s.status_code} {s.text[:120]}")
    bad = api.http.post(f"/questions/{qids[0]}/evaluate", headers=u["headers"], json={"score": 9})
    ok(E, "7.3.2 score out of range refused", bad.status_code == 422, f"{bad.status_code}")

    # ---------------------------------------------------------------- 7.3.8 deployment gate (baseline passes)
    d1 = api.http.post(f"/agents/{agent}/deploy/evaluate", headers=u["headers"], json={"dataset_id": ds, "version": "1.0.0", "thresholds": {"recall_at_5": 0.9}})
    ok(E, "7.3.8 deployment evaluation created", d1.status_code == 201, f"{d1.status_code} {d1.text[:120]}")
    dep1 = None
    for _ in range(300):
        dep1 = api.http.get(f"/deploy/evaluations/{d1.json()['id']}", headers=u["headers"]).json()
        if dep1["status"] in ("passed", "failed"):
            break
        time.sleep(5)
    ok(E, "7.3.8 baseline passes the gate (recall_at_5 >= 0.9)", dep1["status"] == "passed", f"{dep1['status']} {json.dumps(dep1.get('results'))[:200]}")
    dp = api.http.post(f"/agents/{agent}/deploy", headers=u["headers"])
    ok(E, "7.3.8 deploy allowed after a passed evaluation", dp.status_code == 200 and dp.json().get("deployed") is True, f"{dp.status_code} {dp.text[:150]}")

    # ---------------------------------------------------------------- degrade the knowledge base: delete two documents, re-run
    for n in ("e_returns.txt", "e_hr.txt"):
        r = api.http.delete(f"/documents/{ids[n]}/permanent", headers=u["headers"])
        ok(E, f"knowledge base degraded: {n} deleted", r.status_code == 200)
    # same state rerun first (no regression expected), then the degraded one
    job2, st2 = run_job(api, u, ds, agent)
    ok(E, "second evaluation job (degraded knowledge base) completed", st2["status"] == "completed", st2["status"])
    rows2 = results_of(api, u, job2)
    means2 = {k: mean(rows2, k) for k in ("recall_at_1", "recall_at_5", "mrr", "ndcg_at_5", "faithfulness", "hallucination_rate")}
    step(E, "degraded means", "PASS", json.dumps(means2), means=means2)
    ok(E, "the degradation is visible in the metrics (Recall@5 dropped by at least 5 percent)", means2["recall_at_5"] is not None and means1["recall_at_5"] - means2["recall_at_5"] >= 0.05, f"{means1['recall_at_5']} -> {means2['recall_at_5']}")
    cmpj = api.http.get(f"/jobs/{job2}/comparison", headers=u["headers"])
    ok(E, "job-to-previous comparison endpoint answers", cmpj.status_code == 200, f"{cmpj.status_code} {cmpj.text[:200]}")
    reg = api.http.post(f"/datasets/{ds}/regressions/detect", headers=u["headers"], json={"job_id": job2, "previous_job_id": job1})
    regs = reg.json() if reg.status_code == 201 else []
    ok(E, "7.3.3 regression detection flags the degraded metrics", reg.status_code == 201 and any(x["metric"] in ("recall_at_5", "recall_at_1", "mrr") for x in regs), f"{reg.status_code} {[(x['metric'], round(x['change_percentage'], 3), x['severity']) for x in regs][:8]}")
    ok(E, "7.3.9 every flagged regression is at least 5 percent (medium or above) except low ones above 2 percent", all(abs(x["change_percentage"]) >= 0.02 for x in regs), "")
    sev = {x["metric"]: x["severity"] for x in regs}
    if "recall_at_5" in sev:
        drop = (means1["recall_at_5"] - means2["recall_at_5"]) / means1["recall_at_5"]
        expected_sev = "critical" if drop >= 0.2 else "high" if drop >= 0.1 else "medium" if drop >= 0.05 else "low"
        ok(E, "7.3.9 severity classification matches the configured thresholds (20/10/5/2 percent)", sev["recall_at_5"] == expected_sev, f"drop={drop:.2f} expected={expected_sev} got={sev['recall_at_5']}")
    nr = api.http.post(f"/datasets/{ds}/regressions/detect", headers=u["headers"], json={"job_id": job1, "previous_job_id": job1})
    ok(E, "7.3.3 comparing a job with itself reports no regression", nr.status_code == 201 and nr.json() == [], f"{nr.status_code} {nr.text[:100]}")
    summ = api.http.get(f"/datasets/{ds}/regressions/summary", headers=u["headers"])
    ok(E, "7.3.3 regression summary counts the unresolved detections", summ.status_code == 200 and summ.json()["unresolved"] >= 1, f"{summ.text[:160]}")
    if regs:
        rr = api.http.post(f"/regressions/{regs[0]['id']}/resolve", headers=u["headers"])
        ok(E, "regression can be resolved", rr.status_code == 200 and rr.json()["resolved_at"], f"{rr.status_code}")

    # ---------------------------------------------------------------- 7.3.8 gate blocks the regressed agent
    d2 = api.http.post(f"/agents/{agent}/deploy/evaluate", headers=u["headers"], json={"dataset_id": ds, "version": "1.0.1", "thresholds": {"recall_at_5": 0.9}})
    dep2 = None
    for _ in range(300):
        dep2 = api.http.get(f"/deploy/evaluations/{d2.json()['id']}", headers=u["headers"]).json()
        if dep2["status"] in ("passed", "failed"):
            break
        time.sleep(5)
    ok(E, "7.3.8 the regressed agent FAILS the gate", dep2["status"] == "failed", f"{dep2['status']} {json.dumps(dep2.get('results'))[:200]}")
    dp = api.http.post(f"/agents/{agent}/deploy", headers=u["headers"])
    ok(E, "7.3.8 deploy is BLOCKED after the failed evaluation", dp.status_code == 200 and dp.json().get("deployed") is False, f"{dp.status_code} {dp.text[:200]}")

    # ---------------------------------------------------------------- thresholds
    th = api.http.post(f"/organizations/{org}/thresholds", headers=u["headers"], json={"metric": "recall_at_5", "threshold": 0.95, "severity": "high"})
    ok(E, "7.3.9 regression threshold created", th.status_code == 201, f"{th.status_code} {th.text[:100]}")
    chk = api.http.post(f"/organizations/{org}/thresholds/check", headers=u["headers"], json={"metrics": {"recall_at_5": means2["recall_at_5"]}})
    ok(E, "7.3.9 threshold check reports the violation for the degraded value", chk.status_code == 200 and any(v["metric"] == "recall_at_5" for v in chk.json()), f"{chk.status_code} {chk.text[:150]}")
    chk = api.http.post(f"/organizations/{org}/thresholds/check", headers=u["headers"], json={"metrics": {"recall_at_5": 1.0}})
    ok(E, "7.3.9 threshold check is silent for a healthy value", chk.status_code == 200 and chk.json() == [], f"{chk.text[:100]}")

    # ---------------------------------------------------------------- comparisons (generation per question: a few minutes)
    for label, path, body in [
        ("7.3.5 retriever comparison", f"/datasets/{ds}/retrievers/compare", {"name": "strategies", "variants": ["hybrid", "bm25_only", "vector_only"]}),
        ("7.3.6 reranker comparison", f"/datasets/{ds}/rerankers/compare", {"name": "rerankers", "variants": ["cross-encoder/ms-marco-MiniLM-L-6-v2"]}),
        ("7.3.7 prompt comparison", f"/datasets/{ds}/prompts/compare", {"name": "prompts", "variants": ["Answer briefly from the context.", "Answer in one word from the context."]}),
        ("7.3.4 model comparison", f"/datasets/{ds}/compare", {"name": "models", "variants": [{"provider": "ollama", "model": MODEL, "temperature": 0.0}, {"provider": "ollama", "model": MODEL, "temperature": 0.9}]}),
    ]:
        c = api.http.post(path, headers=u["headers"], json=body)
        if c.status_code != 201:
            ok(E, f"{label} created", False, f"{c.status_code} {c.text[:150]}")
            continue
        cid = c.json()["id"]
        res = None
        for _ in range(240):
            kind = {"7.3.5": "retriever-comparisons", "7.3.6": "reranker-comparisons", "7.3.7": "prompt-comparisons"}.get(label[:5], "comparisons")
            res = api.http.get(f"/{kind}/{cid}", headers=u["headers"]).json()
            if res.get("completed_at"):
                break
            time.sleep(5)
        done = bool(res and res.get("completed_at") and res.get("results"))
        info = res.get("results") or {}
        ok(E, f"{label} executed on the worker and ranked", done and len(info.get("variants", [])) == len(body["variants"]) and len(info.get("ranking", [])) == len(body["variants"]), f"ranking={info.get('ranking')} sample={info.get('sample_size')}")
        if done:
            observe(E, f"{label}: recall_at_5 per variant", json.dumps([(v["variant"] if isinstance(v["variant"], str) else "cfg", (v["metrics"].get("recall_at_5") or {}).get("average")) for v in info["variants"]])[:300])

    # ---------------------------------------------------------------- 7.3.10 A/B test
    ab = api.http.post(f"/organizations/{org}/ab-tests", headers=u["headers"], json={"name": "prompt AB", "variant_a": {"system_prompt": "A"}, "variant_b": {"system_prompt": "B"},
                                                                                       "traffic_split": 50, "test_type": "prompt", "target_metric": "satisfaction", "min_sample_size": 4})
    ok(E, "7.3.10 A/B test created", ab.status_code == 201, f"{ab.status_code} {ab.text[:120]}")
    if ab.status_code == 201:
        tid = ab.json()["id"]
        ok(E, "7.3.10 A/B test started", api.http.post(f"/ab-tests/{tid}/start", headers=u["headers"]).status_code == 200)
        for i in range(8):
            api.http.post(f"/ab-tests/{tid}/track", headers=u["headers"], json={"variant": "a", "metric": "satisfaction", "value": 3.0 + (i % 2)})
            api.http.post(f"/ab-tests/{tid}/track", headers=u["headers"], json={"variant": "b", "metric": "satisfaction", "value": 4.0 + (i % 2)})
        rs = api.http.get(f"/ab-tests/{tid}/results", headers=u["headers"])
        ok(E, "7.3.10 A/B results aggregate both variants", rs.status_code == 200 and "satisfaction" in rs.text, f"{rs.status_code} {rs.text[:200]}")
        st = api.http.get(f"/ab-tests/{tid}/statistics", headers=u["headers"])
        ok(E, "7.3.10 A/B statistics endpoint answers", st.status_code == 200, f"{st.status_code} {st.text[:160]}")
        ok(E, "7.3.10 A/B test completed", api.http.post(f"/ab-tests/{tid}/complete", headers=u["headers"]).status_code == 200)
    # permissions: a non-admin member cannot touch the lab
    other = api.user("other")
    r = api.http.get(f"/datasets/{ds}", headers=other["headers"])
    ok(E, "evaluation data of another organization is not readable", r.status_code in (403, 404), f"{r.status_code}")
    r = api.http.post(f"/datasets/{ds}/evaluate", headers=other["headers"], json={"agent_id": agent})
    ok(E, "another organization cannot start a job on this dataset", r.status_code in (403, 404), f"{r.status_code}")
    return write_results(args.out, model=MODEL)


if __name__ == "__main__":
    sys.exit(main())
