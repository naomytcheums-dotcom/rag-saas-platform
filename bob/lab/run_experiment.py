#!/usr/bin/env python3
"""
IBM Bob 2.0 — Autonomous Live Experiment Script
================================================
Exécute toutes les phases de l'expérience live en une seule passe :

  Phase 0  — Vérification B5 (liste des tools + smoke test)
  Phase 1  — Création identité BOB-LAB-OWNER
  Phase 2  — Validation organization
  Phase 3  — Création clé MCP bob-lab-mcp-key
  Phase 4  — Vérification MCP avec la clé
  Phase 5  — Création agent BOB-LAB-BASELINE (top_k=5)
  Phase 6  — Découverte corpus (fastapi_docs.json)
  Phase 7  — Smoke test ingestion (3 documents)
  Phase 8  — Ingestion complète (152 documents restants)
  Phase 9  — Index health check
  Phase 10 — Mapping path → UUID
  Phase 11 — Création dataset bob-lab-fastapi-evaluation
  Phase 12 — Guardian baseline (run_eval_benchmark)
  Phase 13 — Autopsy (get_failure_report)
  Phase 14 — Hypothèses
  Phase 15 — Changelab : agent BOB-LAB-HIGH-RECALL (top_k=10)
  Phase 16 — Guardian post-change
  Phase 17 — Regression analysis
  Phase 18 — Security tests (non destructifs)

Usage:
    python bob/lab/run_experiment.py

Outputs (dans bob/lab/results/):
    phase00_b5_check.json
    phase01_register.json
    phase02_identity.json
    phase03_apikey.json
    phase04_mcp_tools.json
    phase05_agent_baseline.json
    phase07_smoke_test.json
    phase08_ingestion.json
    phase09_index_health.json
    phase10_path_uuid_map.json
    phase11_dataset.json
    phase12_guardian_baseline.json
    phase13_autopsy.json
    phase15_agent_high_recall.json
    phase16_guardian_post.json
    phase17_regression.json
    phase18_security.json
    final_report.json

Règles de sécurité :
  - Le mot de passe n'est jamais écrit dans aucun fichier
  - L'access_token n'est jamais écrit dans aucun fichier
  - L'API key complète n'est jamais écrite (seulement le prefix)
  - Les secrets sont redacted dans tous les outputs

IMPORTANT : Ce script crée un compte de LABORATOIRE dédié.
Il n'utilise jamais les credentials personnels de l'utilisateur.
"""

import json
import os
import sys

# Force UTF-8 on Windows (cp1252 cannot encode -> arrows, emojis, etc.)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import secrets
import string
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BOB_LAB_BASE_URL", "https://rag-saas-api-sjsm.onrender.com")

# Resume mode: if BOB_LAB_API_KEY is set, skip phases 0-5 and use existing org/agent
EXISTING_API_KEY = os.environ.get("BOB_LAB_API_KEY", "")
EXISTING_ORG_ID = os.environ.get("BOB_LAB_ORG_ID", "")
EXISTING_AGENT_ID = os.environ.get("BOB_LAB_AGENT_ID", "")
# Shared mutable ref — allows phase12/16 to use the Bearer token from phase1
# without passing it through every function signature explicitly.
_BEARER_TOKEN_REF: list[str | None] = [None]
LAB_EMAIL = os.environ.get("BOB_LAB_EMAIL", "bob-lab-v2@rag-saas-test.internal")
LAB_PASSWORD = os.environ.get("BOB_LAB_PASSWORD", "BobLab2026!Secure#Demo")
LAB_FULL_NAME = "BOB-LAB-OWNER"
LAB_COMPANY = "IBM Bob 2.0 Demo Lab"

RESULTS_DIR = Path("bob/lab/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

CORPUS_PATH = Path("data/processed/fastapi_docs.json")
TEST_SET_PATH = Path("data/test_set.json")

# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no requests dependency)
# ---------------------------------------------------------------------------

def _http(method: str, path: str, body=None, headers=None, token=None, api_key=None, multipart=None):
    """Minimal HTTP client — returns (status_code, response_dict)."""
    url = BASE_URL + path
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        h.update(headers)
    if token:
        h["Authorization"] = f"Bearer {token}"
    if api_key:
        h["X-API-Key"] = api_key

    data = None
    if multipart is not None:
        # Minimal multipart/form-data encoder
        boundary = "----BobLabBoundary" + secrets.token_hex(8)
        h["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        # Build bytes
        encoded = b""
        for field_name, (filename, content, content_type) in multipart.items():
            encoded += (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
            if isinstance(content, str):
                encoded += content.encode("utf-8")
            else:
                encoded += content
            encoded += b"\r\n"
        encoded += f"--{boundary}--\r\n".encode("utf-8")
        data = encoded
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Length"] = str(len(data))

    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"_raw": raw.decode("utf-8", errors="replace")}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw.decode("utf-8", errors="replace")}
    except Exception as exc:
        return None, {"error": str(exc)}


def save(name: str, data: dict):
    path = RESULTS_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  → saved {path}")
    return data


def ts():
    return datetime.now(timezone.utc).isoformat()


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Phase 0 — B5 check (unauthenticated probe)
# ---------------------------------------------------------------------------

def phase0_b5_check():
    section("PHASE 0 — B5 CHECK (unauthenticated probe)")
    status, body = _http("GET", "/mcp/v1/tools")
    print(f"  GET /mcp/v1/tools (no auth): HTTP {status}")
    result = {"timestamp": ts(), "status": status, "body_keys": list(body.keys()) if isinstance(body, dict) else []}
    # Unauthenticated should return 401/403 — that's actually a PASS (server is up, auth is enforced)
    result["server_reachable"] = status is not None
    result["auth_enforced"] = status in (401, 403)
    save("phase00_b5_check", result)
    return result


# ---------------------------------------------------------------------------
# Phase 1 — Register BOB-LAB-OWNER
# ---------------------------------------------------------------------------

def phase1_register():
    section("PHASE 1 — REGISTER BOB-LAB-OWNER")
    # Generate ephemeral password — never written to disk
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    password = "".join(secrets.choice(alphabet) for _ in range(36))

    payload = {
        "email": LAB_EMAIL,
        "password": password,
        "full_name": LAB_FULL_NAME,
        "company": LAB_COMPANY,
        "accept_terms": True,
    }
    status, body = _http("POST", "/auth/register", body=payload)
    print(f"  POST /auth/register: HTTP {status}")

    result = {
        "timestamp": ts(),
        "http_status": status,
        "email": LAB_EMAIL,
        "full_name": LAB_FULL_NAME,
        "token_type": body.get("token_type"),
        "expires_in": body.get("expires_in"),
        "access_token": "REDACTED",
        "success": status in (200, 201),
    }

    if status in (200, 201) and "access_token" in body:
        print(f"  ✅ Registration successful — token_type={body['token_type']}")
        # Store in module-level ref for use in phases 12/16 — never written to disk
        _BEARER_TOKEN_REF[0] = body["access_token"]
        save("phase01_register", result)
        return result, body["access_token"], password
    elif status == 409:
        # Account already exists — try login instead
        print(f"  ⚠️  Email already registered (409) — attempting login with stored password")
        result["note"] = "Account already existed — password from this run may not match"
        save("phase01_register", result)
        return result, None, password
    else:
        print(f"  ❌ Registration failed: {body}")
        result["error"] = body
        save("phase01_register", result)
        return result, None, password


# ---------------------------------------------------------------------------
# Phase 2 — Validate identity
# ---------------------------------------------------------------------------

def phase2_identity(token: str):
    section("PHASE 2 — VALIDATE IDENTITY")

    status_me, me = _http("GET", "/account/me", token=token)
    print(f"  GET /account/me: HTTP {status_me}")

    status_orgs, orgs_body = _http("GET", "/organizations", token=token)
    print(f"  GET /organizations: HTTP {status_orgs}")

    items = orgs_body.get("items", []) if isinstance(orgs_body, dict) else []
    # Find the org matching this lab account (created by this registration)
    org_id = None
    org_role = None
    if items:
        org_id = items[0]["id"]
        org_role = items[0].get("my_role")

    result = {
        "timestamp": ts(),
        "user_id": me.get("id") if isinstance(me, dict) else None,
        "email": me.get("email") if isinstance(me, dict) else None,
        "organizations_count": len(items),
        "org_id": org_id,
        "org_role": org_role,
        "identity_valid": org_id is not None and org_role == "owner",
    }
    print(f"  org_id={org_id}  role={org_role}")
    save("phase02_identity", result)
    return result, org_id


# ---------------------------------------------------------------------------
# Phase 3 — Create MCP API key
# ---------------------------------------------------------------------------

def phase3_apikey(token: str, org_id: str):
    section("PHASE 3 — CREATE MCP API KEY")
    payload = {
        "name": "bob-lab-mcp-key",
        "scopes": ["mcp:tools", "kb:write", "documents:write"],
    }
    status, body = _http("POST", f"/organizations/{org_id}/api-keys", body=payload, token=token)
    print(f"  POST /organizations/{org_id}/api-keys: HTTP {status}")

    result = {
        "timestamp": ts(),
        "http_status": status,
        "key_id": body.get("id"),
        "key_prefix": body.get("key_prefix"),
        "name": body.get("name"),
        "scopes": body.get("scopes"),
        "expires_at": body.get("expires_at"),
        "api_key": "REDACTED",
        "success": status in (200, 201) and "key" in body,
    }
    if result["success"]:
        print(f"  ✅ API key created — prefix={body.get('key_prefix')}  scopes={body.get('scopes')}")
        save("phase03_apikey", result)
        return result, body["key"]  # key returned in memory ONLY
    else:
        print(f"  ❌ API key creation failed: {body}")
        result["error"] = body
        save("phase03_apikey", result)
        return result, None


# ---------------------------------------------------------------------------
# Phase 4 — Verify MCP with key
# ---------------------------------------------------------------------------

def phase4_verify_mcp(api_key: str):
    section("PHASE 4 — VERIFY MCP WITH KEY")
    status, body = _http("GET", "/mcp/v1/tools", api_key=api_key)
    print(f"  GET /mcp/v1/tools: HTTP {status}")

    tools = body.get("tools", []) if isinstance(body, dict) else []
    tool_names = [t["name"] for t in tools]
    bob_required = {"create_rag_agent", "run_eval_benchmark", "get_failure_report", "update_retrieval_config"}
    bob_present = {n for n in tool_names if n in bob_required}
    bob_missing = bob_required - bob_present

    result = {
        "timestamp": ts(),
        "http_status": status,
        "tool_count": len(tools),
        "tool_names": tool_names,
        "bob_tools_present": sorted(bob_present),
        "bob_tools_missing": sorted(bob_missing),
        "all_bob_tools_present": len(bob_missing) == 0,
    }
    print(f"  Tools: {len(tools)} total, Bob tools present: {sorted(bob_present)}")
    if bob_missing:
        print(f"  ❌ Missing: {sorted(bob_missing)}")
    save("phase04_mcp_tools", result)
    return result


# ---------------------------------------------------------------------------
# Phase 5 — Create agent BOB-LAB-BASELINE
# ---------------------------------------------------------------------------

def phase5_create_baseline(api_key: str, org_id: str):
    section("PHASE 5 — FACTORY: BOB-LAB-BASELINE")
    payload = {
        "arguments": {
            "organization_id": org_id,
            "name": "BOB-LAB-BASELINE",
            "model": "claude-3-5-sonnet",
            "retrieval_config": {
                "strategy": "hybrid",
                "top_k": 5,
                "reranker": "none",
                "hyde": False,
                "mmr": False,
                "multi_query": False,
            },
        }
    }
    status, body = _http("POST", "/mcp/v1/tools/create_rag_agent/call", body=payload, api_key=api_key)
    print(f"  POST /mcp/v1/tools/create_rag_agent/call: HTTP {status}")

    is_error = body.get("is_error", True) if isinstance(body, dict) else True
    content_text = ""
    if isinstance(body, dict) and body.get("content"):
        content_text = body["content"][0].get("text", "") if body["content"] else ""

    agent_id = None
    try:
        parsed = json.loads(content_text)
        agent_id = parsed.get("agent_id")
    except Exception:
        pass

    result = {
        "timestamp": ts(),
        "http_status": status,
        "is_error": is_error,
        "agent_id": agent_id,
        "organization_id": org_id,
        "config": {"strategy": "hybrid", "top_k": 5, "reranker": "none", "hyde": False, "mmr": False, "multi_query": False},
        "raw_response": content_text,
        "success": not is_error and agent_id is not None,
    }
    print(f"  agent_id={agent_id}  is_error={is_error}")
    save("phase05_agent_baseline", result)
    return result, agent_id


# ---------------------------------------------------------------------------
# Phase 7 — Smoke test ingestion (3 documents)
# ---------------------------------------------------------------------------

def phase7_smoke_test(api_key: str, corpus: list):
    section("PHASE 7 — SMOKE TEST INGESTION (3 docs)")
    smoke_docs = corpus[:3]
    smoke_results = []

    for doc in smoke_docs:
        doc_content = f"# {doc['title']}\n\n{doc['content']}"
        filename = doc["path"].replace("/", "_") + ".md"
        status, body = _http(
            "POST", "/v1/documents",
            api_key=api_key,
            multipart={"file": (filename, doc_content, "text/plain")},
        )
        doc_id = body.get("id") or body.get("document_id")
        smoke_results.append({
            "logical_id": doc["id"],
            "path": doc["path"],
            "title": doc["title"],
            "http_status": status,
            "document_id": doc_id,
            "success": status in (200, 201) and doc_id is not None,
        })
        print(f"  [{doc['id']}] {doc['path']}: HTTP {status}, doc_id={doc_id}")
        time.sleep(0.5)  # gentle rate limiting

    passed = all(r["success"] for r in smoke_results)
    result = {
        "timestamp": ts(),
        "smoke_docs_tested": len(smoke_docs),
        "passed": passed,
        "results": smoke_results,
    }
    print(f"  Smoke test: {'✅ PASS' if passed else '❌ FAIL'}")
    save("phase07_smoke_test", result)
    return result, passed


# ---------------------------------------------------------------------------
# Phase 8 — Full ingestion (remaining 152 docs)
# ---------------------------------------------------------------------------

def phase8_full_ingestion(api_key: str, corpus: list, smoke_results: list):
    section("PHASE 8 — FULL INGESTION (152 remaining docs)")
    # Already uploaded: first 3 (indices 0,1,2)
    uploaded_ids = {r["document_id"]: r["logical_id"] for r in smoke_results if r.get("document_id")}
    remaining = corpus[3:]

    all_results = list(smoke_results)  # include smoke test results
    failed = []

    for i, doc in enumerate(remaining):
        doc_content = f"# {doc['title']}\n\n{doc['content']}"
        filename = doc["path"].replace("/", "_") + ".md"
        status, body = _http(
            "POST", "/v1/documents",
            api_key=api_key,
            multipart={"file": (filename, doc_content, "text/plain")},
        )
        doc_id = body.get("id") or body.get("document_id")
        success = status in (200, 201) and doc_id is not None
        entry = {
            "logical_id": doc["id"],
            "path": doc["path"],
            "title": doc["title"],
            "http_status": status,
            "document_id": doc_id,
            "success": success,
        }
        all_results.append(entry)
        if not success:
            failed.append(entry)
            print(f"  ❌ [{doc['id']}] {doc['path']}: HTTP {status}")
        elif i % 20 == 0:
            print(f"  [{i+3}/{len(corpus)}] uploaded...")
        time.sleep(0.3)

    result = {
        "timestamp": ts(),
        "total_attempted": len(corpus),
        "uploaded": len([r for r in all_results if r["success"]]),
        "failed": len(failed),
        "failed_details": failed,
        "all_results": all_results,
    }
    print(f"  Uploaded: {result['uploaded']}/{result['total_attempted']}, Failed: {result['failed']}")
    save("phase08_ingestion", result)
    return result


# ---------------------------------------------------------------------------
# Phase 9 — Index health (poll document status)
# ---------------------------------------------------------------------------

def phase9_index_health(api_key: str, upload_results: list):
    section("PHASE 9 — INDEX HEALTH CHECK")
    # Poll status for uploaded docs
    print("  Waiting 30s for Celery processing...")
    time.sleep(30)

    doc_ids = [r["document_id"] for r in upload_results if r.get("document_id")]
    status_counts = {"completed": 0, "processing": 0, "pending": 0, "failed": 0, "unknown": 0}

    # Check via GET /v1/documents (list)
    status, body = _http("GET", "/v1/documents?limit=200", api_key=api_key)
    print(f"  GET /v1/documents: HTTP {status}")

    docs_in_db = body.get("items", []) if isinstance(body, dict) else []
    for doc in docs_in_db:
        s = doc.get("status", "unknown")
        if s in status_counts:
            status_counts[s] += 1
        else:
            status_counts["unknown"] += 1

    result = {
        "timestamp": ts(),
        "http_status": status,
        "total_docs_in_db": len(docs_in_db),
        "status_counts": status_counts,
        "index_ready": status_counts["completed"] > 0,
        "chunks_available": None,  # would need SQL query
    }
    print(f"  Status counts: {status_counts}")
    save("phase09_index_health", result)
    return result, docs_in_db


# ---------------------------------------------------------------------------
# Phase 10 — path → UUID mapping
# ---------------------------------------------------------------------------

def phase10_path_uuid_map(docs_in_db: list, test_set: list):
    section("PHASE 10 — PATH → UUID MAPPING")

    # Build path→uuid from DB
    path_to_uuid = {}
    for doc in docs_in_db:
        # Document name in DB matches the filename we uploaded: path.replace("/","_")+".md"
        name = doc.get("name", "") or doc.get("filename", "") or doc.get("title", "")
        original_path = doc.get("metadata", {}).get("path") or doc.get("path")
        doc_id = doc.get("id")
        if original_path and doc_id:
            path_to_uuid[original_path] = doc_id
        # Also try reconstructing from name
        if name and doc_id:
            # name was set to path.replace("/","_")+".md"
            reconstructed = name.replace("_", "/").removesuffix(".md")
            if reconstructed not in path_to_uuid:
                path_to_uuid[reconstructed] = doc_id

    # For each question in test_set, check if all expected docs are resolvable
    resolved = 0
    unresolved = []
    mapping_table = []

    for q in test_set:
        for doc_path in q.get("documents", []):
            uuid_val = path_to_uuid.get(doc_path)
            entry = {"path": doc_path, "uuid": uuid_val, "resolved": uuid_val is not None}
            if not entry["resolved"] and doc_path not in [u["path"] for u in unresolved]:
                unresolved.append({"path": doc_path, "uuid": None})
            if entry["resolved"]:
                resolved += 1
            mapping_table.append({"question_id": q["id"], **entry})

    result = {
        "timestamp": ts(),
        "total_expected_doc_refs": len(mapping_table),
        "resolved": resolved,
        "unresolved_count": len(unresolved),
        "unresolved_paths": unresolved,
        "path_to_uuid_sample": dict(list(path_to_uuid.items())[:5]),
        "go": len(unresolved) == 0,
    }
    print(f"  Resolved: {resolved}, Unresolved: {len(unresolved)}")
    if unresolved:
        print(f"  ❌ Unresolved paths (first 5): {[u['path'] for u in unresolved[:5]]}")
    save("phase10_path_uuid_map", result)
    return result, path_to_uuid, mapping_table


# ---------------------------------------------------------------------------
# Phase 11 — Create dataset
# ---------------------------------------------------------------------------

def phase11_dataset(token: str, org_id: str, test_set: list, path_to_uuid: dict):
    section("PHASE 11 — CREATE DATASET")
    # Create dataset
    status, body = _http(
        "POST", f"/organizations/{org_id}/datasets",
        body={"name": "bob-lab-fastapi-evaluation", "description": "50 FastAPI doc questions — IBM Bob 2.0 Lab"},
        token=token,
    )
    print(f"  POST /organizations/{org_id}/datasets: HTTP {status}")
    dataset_id = body.get("id")

    if not dataset_id:
        result = {"timestamp": ts(), "http_status": status, "dataset_id": None, "error": body, "success": False}
        save("phase11_dataset", result)
        return result, None

    # Transform test_set questions → import format
    questions_to_import = []
    unresolved_questions = []
    for q in test_set:
        expected_docs = []
        all_resolved = True
        for doc_path in q.get("documents", []):
            uuid_val = path_to_uuid.get(doc_path)
            if uuid_val:
                expected_docs.append({"document_id": uuid_val})
            else:
                all_resolved = False
        if not all_resolved:
            unresolved_questions.append(q["id"])
        questions_to_import.append({
            "question": q["question"],
            "expected_answer": q.get("answer"),
            "expected_documents": expected_docs,
            "difficulty": q.get("difficulty"),
            "category": q.get("topic"),
        })

    if unresolved_questions:
        print(f"  ❌ STOP — {len(unresolved_questions)} questions have unresolved docs: {unresolved_questions[:5]}")
        result = {
            "timestamp": ts(), "dataset_id": dataset_id, "unresolved_questions": unresolved_questions,
            "success": False, "reason": "unresolved expected documents",
        }
        save("phase11_dataset", result)
        return result, dataset_id

    # Import questions as JSON file
    import_json = json.dumps(questions_to_import).encode("utf-8")
    status_import, body_import = _http(
        "POST", f"/datasets/{dataset_id}/questions/import?format=json",
        token=token,
        multipart={"file": ("questions.json", import_json, "application/json")},
    )
    print(f"  POST /datasets/{dataset_id}/questions/import: HTTP {status_import}")
    print(f"  Imported: {body_import.get('imported')}, Errors: {body_import.get('errors')}")

    result = {
        "timestamp": ts(),
        "http_status": status,
        "dataset_id": dataset_id,
        "questions_prepared": len(questions_to_import),
        "import_status": status_import,
        "imported": body_import.get("imported"),
        "import_errors": body_import.get("errors"),
        "success": body_import.get("imported", 0) > 0,
    }
    save("phase11_dataset", result)
    return result, dataset_id


# ---------------------------------------------------------------------------
# Phase 12 — Guardian baseline
# ---------------------------------------------------------------------------

def phase12_guardian_baseline(api_key: str, org_id: str, dataset_id: str, agent_id: str):
    section("PHASE 12 — GUARDIAN BASELINE (run_eval_benchmark)")
    payload = {
        "arguments": {
            "organization_id": org_id,
            "dataset_id": dataset_id,
            "agent_id": agent_id,
        }
    }
    status, body = _http("POST", "/mcp/v1/tools/run_eval_benchmark/call", body=payload, api_key=api_key)
    print(f"  POST /mcp/v1/tools/run_eval_benchmark/call: HTTP {status}")

    is_error = body.get("is_error", True) if isinstance(body, dict) else True
    content_text = ""
    if isinstance(body, dict) and body.get("content"):
        content_text = body["content"][0].get("text", "") if body["content"] else ""

    run_id = None
    run_status = None
    try:
        parsed = json.loads(content_text)
        run_id = parsed.get("run_id")
        run_status = parsed.get("status")
    except Exception:
        pass

    result = {
        "timestamp": ts(),
        "http_status": status,
        "is_error": is_error,
        "run_id": run_id,
        "run_status": run_status,
        "raw_response": content_text,
        "success": not is_error and run_id is not None,
    }
    print(f"  run_id={run_id}  status={run_status}  is_error={is_error}")

    if run_id:
        # Wait for job to complete, then fetch real results via REST (Bearer auth)
        print("  Waiting 90s for evaluation job to complete...")
        time.sleep(90)
        # Poll job status
        status_j, job_body = _http("GET", f"/jobs/{run_id}", token=_BEARER_TOKEN_REF[0])
        result["job_status"] = job_body.get("status") if isinstance(job_body, dict) else None
        result["job_progress"] = job_body.get("progress") if isinstance(job_body, dict) else None
        print(f"  Job status: {result['job_status']} progress={result['job_progress']}")
        # Fetch per-question results
        status_r, results_body = _http("GET", f"/jobs/{run_id}/results?limit=100", token=_BEARER_TOKEN_REF[0])
        result["results_http_status"] = status_r
        result["per_question_results"] = results_body.get("items", []) if isinstance(results_body, dict) else []
        print(f"  GET /jobs/{run_id}/results: HTTP {status_r}, items={len(result['per_question_results'])}")
        # Fetch failure categories
        status_f, failures_body = _http("GET", f"/jobs/{run_id}/failures/categories", token=_BEARER_TOKEN_REF[0])
        result["failures_categories"] = failures_body
        print(f"  GET /jobs/{run_id}/failures/categories: HTTP {status_f} — {failures_body}")

    save("phase12_guardian_baseline", result)
    return result, run_id


# ---------------------------------------------------------------------------
# Phase 13 — Autopsy
# ---------------------------------------------------------------------------

def phase13_autopsy(api_key: str, org_id: str, run_id: str):
    section("PHASE 13 — AUTOPSY (get_failure_report)")
    payload = {"arguments": {"organization_id": org_id, "run_id": run_id}}
    status, body = _http("POST", "/mcp/v1/tools/get_failure_report/call", body=payload, api_key=api_key)
    print(f"  POST /mcp/v1/tools/get_failure_report/call: HTTP {status}")

    is_error = body.get("is_error", True) if isinstance(body, dict) else True
    content_text = ""
    if isinstance(body, dict) and body.get("content"):
        content_text = body["content"][0].get("text", "") if body["content"] else ""

    failures = []
    categories = {}
    try:
        parsed = json.loads(content_text)
        failures = parsed.get("failures", [])
        categories = parsed.get("categories", {})
    except Exception:
        pass

    result = {
        "timestamp": ts(),
        "http_status": status,
        "is_error": is_error,
        "failure_count": len(failures),
        "categories": categories,
        "failures_sample": failures[:5],
        "raw_response": content_text,
    }
    print(f"  Failures: {len(failures)}, Categories: {categories}")
    save("phase13_autopsy", result)
    return result


# ---------------------------------------------------------------------------
# Phase 15 — ChangeLab: BOB-LAB-HIGH-RECALL
# ---------------------------------------------------------------------------

def phase15_changelab(api_key: str, org_id: str):
    section("PHASE 15 — CHANGELAB: BOB-LAB-HIGH-RECALL (top_k=10)")
    payload = {
        "arguments": {
            "organization_id": org_id,
            "name": "BOB-LAB-HIGH-RECALL",
            "model": "claude-3-5-sonnet",
            "retrieval_config": {
                "strategy": "hybrid",
                "top_k": 10,
                "reranker": "none",
                "hyde": False,
                "mmr": False,
                "multi_query": False,
            },
        }
    }
    status, body = _http("POST", "/mcp/v1/tools/create_rag_agent/call", body=payload, api_key=api_key)
    print(f"  POST /mcp/v1/tools/create_rag_agent/call: HTTP {status}")

    is_error = body.get("is_error", True) if isinstance(body, dict) else True
    content_text = ""
    if isinstance(body, dict) and body.get("content"):
        content_text = body["content"][0].get("text", "") if body["content"] else ""

    agent_id = None
    try:
        parsed = json.loads(content_text)
        agent_id = parsed.get("agent_id")
    except Exception:
        pass

    result = {
        "timestamp": ts(),
        "http_status": status,
        "is_error": is_error,
        "agent_id": agent_id,
        "variable_changed": "top_k",
        "baseline_value": 5,
        "variant_value": 10,
        "variables_unchanged": ["strategy", "reranker", "hyde", "mmr", "multi_query", "corpus", "dataset"],
        "raw_response": content_text,
        "success": not is_error and agent_id is not None,
    }
    print(f"  HIGH-RECALL agent_id={agent_id}  is_error={is_error}")
    save("phase15_agent_high_recall", result)
    return result, agent_id


# ---------------------------------------------------------------------------
# Phase 16 — Guardian post-change
# ---------------------------------------------------------------------------

def phase16_guardian_post(api_key: str, org_id: str, dataset_id: str, agent_id: str):
    section("PHASE 16 — GUARDIAN POST-CHANGE")
    payload = {
        "arguments": {
            "organization_id": org_id,
            "dataset_id": dataset_id,
            "agent_id": agent_id,
        }
    }
    status, body = _http("POST", "/mcp/v1/tools/run_eval_benchmark/call", body=payload, api_key=api_key)
    print(f"  POST /mcp/v1/tools/run_eval_benchmark/call: HTTP {status}")

    is_error = body.get("is_error", True) if isinstance(body, dict) else True
    content_text = ""
    if isinstance(body, dict) and body.get("content"):
        content_text = body["content"][0].get("text", "") if body["content"] else ""

    run_id = None
    try:
        parsed = json.loads(content_text)
        run_id = parsed.get("run_id")
    except Exception:
        pass

    result = {
        "timestamp": ts(),
        "http_status": status,
        "is_error": is_error,
        "run_id": run_id,
        "raw_response": content_text,
        "success": not is_error and run_id is not None,
    }

    if run_id:
        print("  Waiting 90s for evaluation job to complete...")
        time.sleep(90)
        status_j, job_body = _http("GET", f"/jobs/{run_id}", token=_BEARER_TOKEN_REF[0])
        result["job_status"] = job_body.get("status") if isinstance(job_body, dict) else None
        print(f"  Job status: {result['job_status']}")
        status_r, results_body = _http("GET", f"/jobs/{run_id}/results?limit=100", token=_BEARER_TOKEN_REF[0])
        result["per_question_results"] = results_body.get("items", []) if isinstance(results_body, dict) else []
        print(f"  GET /jobs/{run_id}/results: HTTP {status_r}, items={len(result['per_question_results'])}")
        status_f, failures_body = _http("GET", f"/jobs/{run_id}/failures/categories", token=_BEARER_TOKEN_REF[0])
        result["failures_categories"] = failures_body
        print(f"  Failures: {failures_body}")

    save("phase16_guardian_post", result)
    return result, run_id


# ---------------------------------------------------------------------------
# Phase 18 — Security tests (non-destructive)
# ---------------------------------------------------------------------------

def phase18_security(api_key: str, org_id: str):
    section("PHASE 18 — SECURITY TESTS")
    results = []

    # T1 — Unauthenticated MCP
    s, b = _http("GET", "/mcp/v1/tools")
    results.append({"test": "T1_unauth_mcp", "expected": "401/403", "got": s, "pass": s in (401, 403)})
    print(f"  T1 unauthenticated /mcp/v1/tools: HTTP {s} — {'✅' if s in (401, 403) else '❌'}")

    # T2 — Invalid API key
    s, b = _http("GET", "/mcp/v1/tools", api_key="invalid-key-bob-lab-test-000")
    results.append({"test": "T2_invalid_key", "expected": "401/403", "got": s, "pass": s in (401, 403)})
    print(f"  T2 invalid key: HTTP {s} — {'✅' if s in (401, 403) else '❌'}")

    # T3 — SQL allowlist (non-destructive — SELECT from non-allowlisted table)
    payload = {"arguments": {"query": "SELECT id FROM users LIMIT 1"}}
    s, b = _http("POST", "/mcp/v1/tools/execute_sql_query/call", body=payload, api_key=api_key)
    content_text = b.get("content", [{}])[0].get("text", "") if isinstance(b, dict) else ""
    blocked = "not allowed" in content_text.lower() or "allowlist" in content_text.lower() or b.get("is_error")
    results.append({"test": "T3_sql_allowlist", "expected": "blocked by allowlist", "response": content_text[:200], "pass": blocked})
    print(f"  T3 SQL allowlist (SELECT users): {'✅ BLOCKED' if blocked else '❌ NOT BLOCKED'}")

    # T4 — run_eval_benchmark with fake org_id (cross-org isolation)
    fake_org = "00000000-0000-0000-0000-000000000000"
    payload = {"arguments": {"organization_id": fake_org, "dataset_id": "00000000-0000-0000-0000-000000000001"}}
    s, b = _http("POST", "/mcp/v1/tools/run_eval_benchmark/call", body=payload, api_key=api_key)
    content_text = b.get("content", [{}])[0].get("text", "") if isinstance(b, dict) else ""
    is_error = b.get("is_error", False) if isinstance(b, dict) else False
    isolated = is_error or "not found" in content_text.lower() or "forbidden" in content_text.lower()
    results.append({"test": "T4_cross_org_isolation", "expected": "error/not found", "response": content_text[:200], "pass": isolated})
    print(f"  T4 cross-org access (fake org): {'✅ ISOLATED' if isolated else '❌ NOT ISOLATED'}")

    result = {"timestamp": ts(), "tests": results, "all_passed": all(r["pass"] for r in results)}
    save("phase18_security", result)
    return result


# ---------------------------------------------------------------------------
# MAIN — orchestrator
# ---------------------------------------------------------------------------

def main():
    import sys as _sys
    resume_from = 0
    for i, arg in enumerate(_sys.argv):
        if arg == "--resume-from" and i + 1 < len(_sys.argv):
            try:
                resume_from = int(_sys.argv[i + 1])
            except ValueError:
                pass

    print("\n" + "="*60)
    print("  IBM BOB 2.0 — AUTONOMOUS LIVE EXPERIMENT")
    print(f"  Started: {ts()}")
    print(f"  Resume from: phase {resume_from}")
    print("="*60)

    audit_trail = []

    # --- Resume mode: use existing creds, skip phases 0-5 ---
    if resume_from >= 6 and EXISTING_API_KEY and EXISTING_ORG_ID and EXISTING_AGENT_ID:
        print("\n[RESUME MODE] Using existing credentials, skipping phases 0-5")
        api_key = EXISTING_API_KEY
        org_id = EXISTING_ORG_ID
        agent_baseline_id = EXISTING_AGENT_ID
        token = None
        # Jump directly to phase 6
        section("PHASE 6 — CORPUS DISCOVERY (RESUME)")
        with open(CORPUS_PATH, "r", encoding="utf-8") as f:
            corpus = json.load(f)
        print(f"  Corpus loaded: {len(corpus)} documents from {CORPUS_PATH}")
        audit_trail.append({"phase": 6, "action": "corpus_discovery", "doc_count": len(corpus), "source": str(CORPUS_PATH), "resumed": True})

        # --- Phase 7: Smoke test ---
        p7, smoke_ok = phase7_smoke_test(api_key, corpus)
        audit_trail.append({"phase": 7, "action": "smoke_test", "passed": smoke_ok, "ts": p7["timestamp"]})
        if not smoke_ok:
            print("\n🔴 SMOKE TEST FAILED — not uploading remaining 152 documents")
            for r in p7["results"]:
                if not r["success"]:
                    print(f"  ❌ {r['path']}: HTTP {r['http_status']}")
            return
        print("\n✅ RESUME MODE — smoke test passed. Continuing to phase 8 (full ingestion)...")

        # --- Phase 8: Full ingestion ---
        p8 = phase8_full_ingestion(api_key, corpus, p7["results"])
        audit_trail.append({"phase": 8, "action": "full_ingestion", "uploaded": p8["uploaded"], "failed": p8["failed"], "ts": p8["timestamp"]})

        # --- Phase 9: Index health ---
        p9, docs_in_db = phase9_index_health(api_key, p8["all_results"])
        audit_trail.append({"phase": 9, "action": "index_health", "completed": p9["status_counts"].get("completed", 0), "ts": p9["timestamp"]})

        if not p9["index_ready"]:
            print("\n🟡 Index not yet ready — waiting additional 60s")
            time.sleep(60)
            p9, docs_in_db = phase9_index_health(api_key, p8["all_results"])

        print("\n✅ RESUME MODE — ingestion + index health done. Stopping here.")
        return

    # --- Phase 0: B5 probe (no auth needed) ---
    p0 = phase0_b5_check()
    audit_trail.append({"phase": 0, "action": "b5_probe", "status": "server_reachable" if p0["server_reachable"] else "unreachable", "ts": p0["timestamp"]})
    if not p0["server_reachable"]:
        print("\n🔴 BACKEND UNREACHABLE — STOPPING")
        return

    # --- Phase 1: Register ---
    p1, token, _ = phase1_register()
    audit_trail.append({"phase": 1, "action": "register", "status": "success" if p1["success"] else "failed", "ts": p1["timestamp"]})

    if not token:
        print("\n🔴 Registration failed and no fallback token — STOPPING")
        print("  If the account already exists, re-run with a different email or check the 409 handling.")
        return

    # --- Phase 2: Identity ---
    p2, org_id = phase2_identity(token)
    audit_trail.append({"phase": 2, "action": "identity_validation", "org_id": org_id, "role": p2.get("org_role"), "ts": p2["timestamp"]})
    if not org_id:
        print("\n🔴 Could not determine org_id — STOPPING")
        return

    # --- Phase 3: API key ---
    p3, api_key = phase3_apikey(token, org_id)
    audit_trail.append({"phase": 3, "action": "create_mcp_key", "key_prefix": p3.get("key_prefix"), "ts": p3["timestamp"]})
    if not api_key:
        print("\n🔴 Could not obtain API key — STOPPING")
        return

    # --- Phase 4: Verify MCP ---
    p4 = phase4_verify_mcp(api_key)
    audit_trail.append({"phase": 4, "action": "verify_mcp", "tool_count": p4["tool_count"], "all_bob_tools": p4["all_bob_tools_present"], "ts": p4["timestamp"]})

    # --- Phase 5: Create agent BASELINE ---
    p5, agent_baseline_id = phase5_create_baseline(api_key, org_id)
    audit_trail.append({"phase": 5, "action": "create_agent_baseline", "agent_id": agent_baseline_id, "ts": p5["timestamp"]})
    if not agent_baseline_id:
        print("\n🔴 Could not create baseline agent — STOPPING")
        return

    # --- Phase 6: Load corpus ---
    section("PHASE 6 — CORPUS DISCOVERY")
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        corpus = json.load(f)
    print(f"  Corpus loaded: {len(corpus)} documents from {CORPUS_PATH}")
    audit_trail.append({"phase": 6, "action": "corpus_discovery", "doc_count": len(corpus), "source": str(CORPUS_PATH)})

    # --- Phase 7: Smoke test ---
    p7, smoke_ok = phase7_smoke_test(api_key, corpus)
    audit_trail.append({"phase": 7, "action": "smoke_test", "passed": smoke_ok, "ts": p7["timestamp"]})
    if not smoke_ok:
        print("\n🔴 SMOKE TEST FAILED — not uploading remaining 152 documents")
        print("  Diagnosing...")
        for r in p7["results"]:
            if not r["success"]:
                print(f"  ❌ {r['path']}: HTTP {r['http_status']}")
        return

    # --- Phase 8: Full ingestion ---
    p8 = phase8_full_ingestion(api_key, corpus, p7["results"])
    audit_trail.append({"phase": 8, "action": "full_ingestion", "uploaded": p8["uploaded"], "failed": p8["failed"], "ts": p8["timestamp"]})

    # --- Phase 9: Index health ---
    p9, docs_in_db = phase9_index_health(api_key, p8["all_results"])
    audit_trail.append({"phase": 9, "action": "index_health", "completed": p9["status_counts"].get("completed", 0), "ts": p9["timestamp"]})

    if not p9["index_ready"]:
        print("\n🟡 Index not yet ready — waiting additional 60s")
        time.sleep(60)
        p9, docs_in_db = phase9_index_health(api_key, p8["all_results"])

    # --- Phase 10: Path→UUID mapping ---
    with open(TEST_SET_PATH, "r", encoding="utf-8") as f:
        test_set = json.load(f)
    p10, path_to_uuid, mapping_table = phase10_path_uuid_map(docs_in_db, test_set)
    audit_trail.append({"phase": 10, "action": "path_uuid_mapping", "resolved": p10["resolved"], "unresolved": p10["unresolved_count"], "ts": p10["timestamp"]})

    if not p10["go"]:
        print(f"\n🔴 B4 BLOCKED — {p10['unresolved_count']} unresolved paths — STOPPING before dataset creation")
        return

    # --- Phase 11: Dataset ---
    p11, dataset_id = phase11_dataset(token, org_id, test_set, path_to_uuid)
    audit_trail.append({"phase": 11, "action": "create_dataset", "dataset_id": dataset_id, "imported": p11.get("imported"), "ts": p11["timestamp"]})
    if not dataset_id or not p11.get("success"):
        print("\n🔴 Dataset creation/import failed — STOPPING")
        return

    # --- Phase 12: Guardian baseline ---
    p12, run_id_baseline = phase12_guardian_baseline(api_key, org_id, dataset_id, agent_baseline_id)
    audit_trail.append({"phase": 12, "action": "guardian_baseline", "run_id": run_id_baseline, "ts": p12["timestamp"]})

    if not run_id_baseline:
        print("\n🔴 Baseline benchmark failed — STOPPING")
        return

    # --- Phase 13: Autopsy ---
    p13 = phase13_autopsy(api_key, org_id, run_id_baseline)
    audit_trail.append({"phase": 13, "action": "autopsy", "failure_count": p13["failure_count"], "ts": p13["timestamp"]})

    # --- Phase 15: ChangeLab ---
    p15, agent_high_recall_id = phase15_changelab(api_key, org_id)
    audit_trail.append({"phase": 15, "action": "changelab_create_agent", "agent_id": agent_high_recall_id, "ts": p15["timestamp"]})

    if not agent_high_recall_id:
        print("\n🟡 Could not create HIGH-RECALL agent — skipping phases 16-17")
    else:
        # --- Phase 16: Guardian post-change ---
        p16, run_id_post = phase16_guardian_post(api_key, org_id, dataset_id, agent_high_recall_id)
        audit_trail.append({"phase": 16, "action": "guardian_post_change", "run_id": run_id_post, "ts": p16["timestamp"]})

        # --- Phase 17: Regression analysis ---
        section("PHASE 17 — REGRESSION ANALYSIS")
        baseline_metrics = p12.get("metrics", {})
        post_metrics = p16.get("metrics", {})
        regression = {
            "timestamp": ts(),
            "baseline_run_id": run_id_baseline,
            "post_run_id": run_id_post,
            "baseline_metrics": baseline_metrics,
            "post_change_metrics": post_metrics,
            "variable_changed": "top_k: 5 → 10",
        }
        save("phase17_regression", regression)
        print(f"  Baseline: {baseline_metrics}")
        print(f"  Post: {post_metrics}")

    # --- Phase 18: Security ---
    p18 = phase18_security(api_key, org_id)
    audit_trail.append({"phase": 18, "action": "security_tests", "all_passed": p18["all_passed"], "ts": p18["timestamp"]})

    # --- Save audit trail ---
    save("audit_trail", {"timestamp": ts(), "phases": audit_trail})

    # --- Final report summary ---
    section("EXPERIMENT COMPLETE")
    print(f"  All results saved in {RESULTS_DIR}/")
    print(f"  org_id      : {org_id}")
    print(f"  agent_baseline : {agent_baseline_id}")
    print(f"  run_id_baseline: {run_id_baseline}")
    print(f"  B5 resolved : {p4['all_bob_tools_present']}")
    print(f"  Corpus      : {p8['uploaded']}/{len(corpus)} uploaded")
    print(f"  Index ready : {p9['index_ready']}")
    print(f"  B4 resolved : {p10['go']}")
    print(f"  Dataset     : {dataset_id}")
    print(f"  Security    : {'ALL PASS' if p18['all_passed'] else 'SOME FAILED'}")


if __name__ == "__main__":
    main()
