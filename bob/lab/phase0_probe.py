#!/usr/bin/env python3
"""
IBM Bob 2.0 — Phase 0 probe script.
Tente GET /mcp/v1/tools sur le backend live pour vérifier B5.
Écrit le résultat dans bob/lab/phase0_result.json.
Usage: python bob/lab/phase0_probe.py <X_API_KEY>
"""
import json
import sys
import urllib.request
import urllib.error

BASE_URL = "https://rag-saas-api-sjsm.onrender.com"
API_KEY = sys.argv[1] if len(sys.argv) > 1 else None

def get(path, headers=None):
    req = urllib.request.Request(BASE_URL + path, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return None, {"error": str(e)}

results = {}

# Test 1 — unauthenticated /mcp/v1/tools
status, body = get("/mcp/v1/tools")
results["unauth_mcp_tools"] = {"status": status, "body": body}
print(f"[T1] GET /mcp/v1/tools (no auth): {status}")

# Test 2 — authenticated /mcp/v1/tools (if key provided)
if API_KEY:
    status, body = get("/mcp/v1/tools", {"X-API-Key": API_KEY})
    results["auth_mcp_tools"] = {"status": status, "tool_count": len(body.get("tools", [])), "tool_names": [t["name"] for t in body.get("tools", [])]}
    print(f"[T2] GET /mcp/v1/tools (with key): {status}, tools: {results['auth_mcp_tools']['tool_count']}")
    # Check 4 Bob tools
    bob_tools = {"create_rag_agent", "run_eval_benchmark", "get_failure_report", "update_retrieval_config"}
    present = {t for t in results["auth_mcp_tools"]["tool_names"] if t in bob_tools}
    results["bob_tools_present"] = sorted(present)
    results["bob_tools_missing"] = sorted(bob_tools - present)
    print(f"[T2] Bob tools present: {sorted(present)}")
    print(f"[T2] Bob tools missing: {sorted(bob_tools - present)}")

with open("bob/lab/phase0_result.json", "w") as f:
    json.dump(results, f, indent=2)

print("[DONE] Results saved to bob/lab/phase0_result.json")
