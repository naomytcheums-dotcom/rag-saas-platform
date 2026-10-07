"""One real end-to-end journey against a RUNNING API (default http://127.0.0.1:8000), through the real worker, S3, database and model:

    register -> create organization -> upload a small text document (S3) -> wait for the Celery worker to index it
    -> search (retrieval) -> create an agent -> ask a question through /chat/stream -> check the answer and its citations -> clean up.

Run the API and a Celery worker first (see docs/operations). Every step prints PASS/FAIL with the real status code or error; nothing secret is printed.
The throw-away account and organization are deleted at the end, even when a step failed.

    python scripts/real_journey.py [--base http://127.0.0.1:8000] [--wait 240] [--keep]
"""

import argparse
import json
import sys
import time
import uuid

import httpx

SECRET_FACT = "The Zorblax support line opens every Tuesday at 14:30 Douala time and the escalation code is PELICAN-7421."
DOCUMENT = (
    "Zorblax Internal Handbook\n\n"
    "Section 1. Support hours. " + SECRET_FACT + " Customers must quote their ticket number.\n\n"
    "Section 2. Refunds. A refund is possible within 14 days of purchase when the invoice number is provided.\n"
)
QUESTION = "When does the Zorblax support line open, and what is the escalation code?"

results: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--wait", type=int, default=240, help="seconds to wait for the worker to index the document")
    parser.add_argument("--keep", action="store_true", help="do not delete the throw-away organization at the end")
    args = parser.parse_args()
    http = httpx.Client(base_url=args.base, timeout=httpx.Timeout(120.0, connect=15.0))
    suffix = uuid.uuid4().hex[:10]
    email, password = f"journey-{suffix}@example.com", f"Journey-{uuid.uuid4().hex}-Aa1!"
    headers, org_id = {}, None
    try:
        r = http.get("/health")
        if not step("API reachable", r.status_code == 200, f"GET /health -> {r.status_code}"):
            return 1

        r = http.post("/auth/register", json={"email": email, "password": password, "full_name": "Journey Test", "accept_terms": True})
        if not step("register", r.status_code in (200, 201), f"{r.status_code} {'' if r.status_code < 300 else r.text[:200]}"):
            return 1
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = http.post("/organizations", json={"name": f"Journey {suffix}"}, headers=headers)
        if not step("create organization", r.status_code in (200, 201), f"{r.status_code} {'' if r.status_code < 300 else r.text[:200]}"):
            return 1
        org_id = r.json()["id"]

        r = http.post(f"/organizations/{org_id}/documents", headers=headers, files={"file": ("zorblax_handbook.txt", DOCUMENT.encode(), "text/plain")})
        if not step("upload document (S3)", r.status_code in (200, 201, 202), f"{r.status_code} {'' if r.status_code < 300 else r.text[:300]}"):
            return 1
        document = r.json()
        document_id = document.get("id") or (document.get("document") or {}).get("id")
        print(f"      status right after upload: {document.get('status')}", flush=True)

        deadline, status, last = time.time() + args.wait, document.get("status"), None
        while time.time() < deadline and status not in ("completed", "ready", "indexed", "failed", "error"):
            time.sleep(5)
            listing = http.get(f"/organizations/{org_id}/documents", headers=headers)
            items = listing.json() if listing.status_code == 200 else []
            items = items if isinstance(items, list) else next((v for v in items.values() if isinstance(v, list)), [])
            mine = next((d for d in items if d.get("id") == document_id), None)
            last, status = mine, (mine or {}).get("status", status)
        step("worker indexed the document", status in ("completed", "ready", "indexed"), f"final status={status!r} " + (str({k: v for k, v in (last or {}).items() if "error" in k or k in ("chunk_count",)})[:200]))

        r = http.post(f"/organizations/{org_id}/search", headers=headers, json={"query": QUESTION, "top_k": 3})
        body = r.json() if r.status_code == 200 else {}
        hits = body if isinstance(body, list) else next((v for v in body.values() if isinstance(v, list)), []) if isinstance(body, dict) else []
        found = any("PELICAN-7421" in json.dumps(h) for h in hits)
        step("retrieval finds the planted fact", r.status_code == 200 and found, f"{r.status_code}, {len(hits)} hits, fact in top results: {found}")

        r = http.post(f"/organizations/{org_id}/agents", headers=headers, json={"name": f"Journey agent {suffix}", "system_prompt": "Answer only from the provided documents and cite them."})
        if not step("create agent", r.status_code in (200, 201), f"{r.status_code} {'' if r.status_code < 300 else r.text[:300]}"):
            return 1
        agent_id = r.json()["id"]

        events, text, error, citations = [], "", None, 0
        with http.stream("POST", "/chat/stream", headers=headers, json={"agent_id": agent_id, "message": QUESTION}) as stream:
            status_code = stream.status_code
            for line in stream.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload in ("", "[DONE]"):
                    continue
                try:
                    event = json.loads(payload)
                except ValueError:
                    continue
                kind = event.get("type") or event.get("event") or "chunk"
                events.append(kind)
                text += str(event.get("content") or event.get("text") or event.get("delta") or "")
                if kind == "error" or event.get("error"):
                    error = str(event.get("error") or event.get("message") or event)[:300]
                citations += len(event.get("citations") or []) if isinstance(event.get("citations"), list) else (1 if kind == "citation" else 0)
        step("chat stream answers without error", status_code == 200 and error is None and len(text) > 0, f"HTTP {status_code}, events={sorted(set(events))}, answer {len(text)} chars" + (f", ERROR: {error}" if error else ""))
        step("answer is grounded in the document", "PELICAN-7421" in text or "14:30" in text, f"answer starts: {text[:160]!r}")
        step("answer carries citations", citations > 0, f"{citations} citation events/items")
    finally:
        if org_id and not args.keep:
            r = http.delete(f"/organizations/{org_id}", headers=headers)
            step("cleanup: delete throw-away organization", r.status_code in (200, 202, 204), f"{r.status_code}")
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} steps passed" + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
