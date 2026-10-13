"""Shared helpers of the "RAG value chain with Ollama" validation scripts (scripts/e2e_rag_ingestion_search.py, e2e_rag_chat_scenarios.py).

Every helper talks to a RUNNING local stack (API on 127.0.0.1, own Celery worker, real Ollama, real PostgreSQL/pgvector, real MinIO). No mock.
Refuses to run against anything that is not a local address.
"""

import asyncio
import io
import json
import os
import re
import subprocess
import time
import uuid
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
LOCAL_RE = re.compile(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$")
RESULTS: list[dict] = []


def require_local(base: str) -> None:
    if not LOCAL_RE.match(base):
        raise SystemExit("REFUSED: these scripts only run against a local API")


def step(phase: str, name: str, status: str, detail: str = "", **evidence) -> bool:
    RESULTS.append({"phase": phase, "name": name, "status": status, "detail": detail, **evidence})
    print(f"[{status}] {phase} / {name}" + (f" -- {detail}" if detail else ""), flush=True)
    return status == "PASS"


def ok(phase: str, name: str, condition: bool, detail: str = "", **evidence) -> bool:
    return step(phase, name, "PASS" if condition else "FAIL", detail, **evidence)


def observe(phase: str, name: str, detail: str, **evidence) -> None:
    """Recorded measurement that is not judged (clearly labelled as an observation)."""
    step(phase, "OBSERVATION: " + name, "PASS", detail, **evidence)


def write_results(path: str, **extra) -> int:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"results": RESULTS, "generated": time.strftime("%Y-%m-%d %H:%M:%S"), **extra}, fh, indent=1, ensure_ascii=False)
    counts = {s: sum(1 for x in RESULTS if x["status"] == s) for s in ("PASS", "FAIL", "BLOCKED")}
    print(f"\nSUMMARY {counts}  (details in {path})", flush=True)
    return 1 if counts["FAIL"] else 0


# ------------------------------------------------------------------ database (asyncpg, direct, read-only checks)
def _pg_dsn() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1" not in url and "localhost" not in url:
        raise SystemExit("REFUSED: DATABASE_URL must be local (source scripts/test_env/rag_stack_env.sh)")
    return url.replace("postgresql+asyncpg://", "postgresql://")


def sql(query: str, *args):
    import asyncpg

    async def run():
        conn = await asyncpg.connect(_pg_dsn())
        try:
            return await conn.fetch(query, *args)
        finally:
            await conn.close()

    return asyncio.run(run())


def sql_exec(query: str, *args):
    import asyncpg

    async def run():
        conn = await asyncpg.connect(_pg_dsn())
        try:
            return await conn.execute(query, *args)
        finally:
            await conn.close()

    return asyncio.run(run())


def s3_exists(key: str, bucket: str = "documents") -> bool:
    import boto3
    from botocore.exceptions import ClientError

    c = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT_URL"], aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
                     aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"], region_name="us-east-1")
    try:
        c.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


# ------------------------------------------------------------------ worker control (private worker only)
def worker_ctl(action: str) -> None:
    """Stop/start the PRIVATE Celery worker started by scripts/test_env/rag_stack_start.sh (pid file in RAG_LOG_DIR)."""
    log_dir = Path(os.environ.get("RAG_LOG_DIR", "."))
    pid_file = log_dir / "rag_worker.pid"
    if action == "stop":
        # the pid file holds the shell's pid; kill the whole celery process tree started with node name rag14
        subprocess.run(["C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'celery' -and $_.CommandLine -match 'rag14@' } | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], check=False)
    elif action == "start":
        subprocess.Popen(["C:/Program Files/Git/bin/bash.exe", "-c", f"cd '{ROOT.as_posix()}' && export PATH=\"/c/Users/NITROV15/Downloads/rag-saas-platform/.venv/Scripts:$PATH\" && "
                          f"source scripts/test_env/rag_stack_env.sh && nohup python -m celery -A api.tasks.celery_app worker -P solo -l info -n rag14@%h "
                          f">> '{(log_dir / 'rag_worker.log').as_posix()}' 2>&1 &"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _ = pid_file


# ------------------------------------------------------------------ file builders
def minimal_pdf(text: str) -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def make_docx(paragraphs: list[str]) -> bytes:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_epub(title: str, chapters: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        manifest = "".join(f'<item id="c{i}" href="c{i}.xhtml" media-type="application/xhtml+xml"/>' for i in range(len(chapters)))
        spine = "".join(f'<itemref idref="c{i}"/>' for i in range(len(chapters)))
        z.writestr("content.opf", '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
                   f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title><dc:identifier id="id">urn:uuid:{uuid.uuid4()}</dc:identifier>'
                   f'<dc:language>en</dc:language></metadata><manifest>{manifest}</manifest><spine>{spine}</spine></package>')
        for i, text in enumerate(chapters):
            z.writestr(f"c{i}.xhtml", f'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>c{i}</title></head><body><p>{text}</p></body></html>')
    return buf.getvalue()


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


# ------------------------------------------------------------------ API client
class Api:
    def __init__(self, base: str):
        require_local(base)
        self.http = httpx.Client(base_url=base, timeout=httpx.Timeout(900.0, connect=15.0))

    def user(self, label: str, org_name: str | None = None, with_org: bool = True):
        email, pw = f"rag-{label}-{uuid.uuid4().hex[:8]}@example.com", f"Rag-{uuid.uuid4().hex}-Aa1!"
        r = self.http.post("/auth/register", json={"email": email, "password": pw, "full_name": f"RAG {label}", "accept_terms": True})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"register failed {r.status_code} {r.text[:200]}")
        headers = {"Authorization": "Bearer " + r.json()["access_token"]}
        out = {"email": email, "password": pw, "headers": headers, "user_id": r.json().get("user", {}).get("id")}
        if with_org:
            org = self.http.post("/organizations", json={"name": org_name or f"RAG {label} {uuid.uuid4().hex[:6]}"}, headers=headers).json()
            out["org_id"] = org["id"]
        return out

    def settings(self, user, **kw):
        return self.http.patch(f"/organizations/{user['org_id']}/settings", headers=user["headers"], json=kw)

    def upload(self, user, name: str, content: bytes, ctype: str = "application/octet-stream"):
        return self.http.post(f"/organizations/{user['org_id']}/documents", headers=user["headers"], files={"file": (name, content, ctype)})

    def docs(self, user) -> list[dict]:
        out, offset = [], 0
        while True:
            r = self.http.get(f"/organizations/{user['org_id']}/documents", headers=user["headers"], params={"limit": 200, "offset": offset})
            body = r.json() if r.status_code == 200 else []
            items = body if isinstance(body, list) else body.get("items", next((v for v in body.values() if isinstance(v, list)), []))
            out += items
            if len(items) < 200:
                return out
            offset += 200

    def wait(self, user, ids, timeout: int = 600, poll: float = 3.0, terminal=("completed", "failed", "error")) -> dict[str, dict]:
        ids = set(ids)
        deadline, final = time.time() + timeout, {}
        while time.time() < deadline and len(final) < len(ids):
            for d in self.docs(user):
                if d.get("id") in ids and d.get("status") in terminal:
                    final[d["id"]] = d
            if len(final) < len(ids):
                time.sleep(poll)
        return final

    def wait_reprocessed(self, user, doc_id, before_started, timeout: int = 600, poll: float = 2.0) -> dict:
        """Wait until the document has been (re)processed AFTER `before_started` (its previous indexing_started_at): reindex / replace flip the status
        asynchronously, so a plain wait on a terminal status returns at once with the old state."""
        deadline = time.time() + timeout
        st = {}
        while time.time() < deadline:
            st = self.status_of(doc_id, user)
            if st.get("indexing_started_at") != before_started and st.get("status") in ("completed", "failed", "error"):
                return st
            time.sleep(poll)
        return st

    def status_of(self, doc_id, user) -> dict:
        r = self.http.get(f"/documents/{doc_id}/status", headers=user["headers"])
        return r.json() if r.status_code == 200 else {"http": r.status_code}

    def search(self, user, query, **kw):
        body = {"query": query, **kw}
        r = self.http.post(f"/organizations/{user['org_id']}/search", headers=user["headers"], json=body)
        return r.status_code, (r.json().get("results", []) if r.status_code == 200 else r.text[:200])

    def chat(self, headers, agent_id, message, conversation_id=None, timeout=None):
        events, text, error, citations = [], "", None, []
        started = time.time()
        body = {"agent_id": agent_id, "message": message}
        if conversation_id:
            body["conversation_id"] = conversation_id
        conv = None
        first_token = None
        try:
            with self.http.stream("POST", "/chat/stream", headers=headers, json=body, timeout=timeout or httpx.Timeout(900.0, connect=15.0)) as stream:
                code, sse_event = stream.status_code, None
                if code != 200:
                    return {"status": code, "text": "", "error": stream.read().decode()[:300], "citations": [], "events": [], "seconds": round(time.time() - started, 1),
                            "conversation_id": None, "first_token_s": None}
                for line in stream.iter_lines():
                    if line.startswith("event:"):
                        sse_event = line[6:].strip()
                        continue
                    if not line.startswith("data:"):
                        if not line:
                            sse_event = None
                        continue
                    payload = line[5:].strip()
                    if payload in ("", "[DONE]"):
                        continue
                    try:
                        ev = json.loads(payload)
                    except ValueError:
                        continue
                    kind = sse_event or ev.get("type") or "chunk"
                    events.append(kind)
                    conv = ev.get("conversation_id") or conv
                    if kind == "token":
                        if first_token is None:
                            first_token = round(time.time() - started, 1)
                        text += str(ev.get("token") or "")
                    elif kind == "citation":
                        citations.append(ev)
                    elif kind == "error" or ev.get("error"):
                        error = str(ev.get("error") or ev)[:300]
                    elif kind == "done" and isinstance(ev.get("citations"), list):
                        citations.extend(ev["citations"])
        except httpx.HTTPError as exc:
            return {"status": 0, "text": text, "error": f"transport: {type(exc).__name__}: {exc}"[:300], "citations": citations, "events": sorted(set(events)),
                    "seconds": round(time.time() - started, 1), "conversation_id": conv, "first_token_s": first_token}
        return {"status": code, "text": text, "error": error, "citations": citations, "events": sorted(set(events)), "seconds": round(time.time() - started, 1),
                "conversation_id": conv, "first_token_s": first_token}


def metrics(rank_lists: list[tuple[list[str], set[str]]]) -> dict:
    """Recall@k (any expected document within the top k), MRR, NDCG@10 (binary relevance) over (ranked document ids, expected set) pairs."""
    import math

    n = len(rank_lists) or 1
    out = {"n": len(rank_lists)}
    for k in (1, 3, 5, 10):
        out[f"recall@{k}"] = round(sum(1 for r, e in rank_lists if e & set(r[:k])) / n, 3)
    rr = ndcg = 0.0
    for ranked, expected in rank_lists:
        for pos, d in enumerate(ranked, 1):
            if d in expected:
                rr += 1.0 / pos
                break
        dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(ranked[:10]) if d in expected)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(expected), 10)))
        ndcg += dcg / idcg if idcg else 0.0
    out["mrr"] = round(rr / n, 3)
    out["ndcg@10"] = round(ndcg / n, 3)
    return out
