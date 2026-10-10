"""Post-deploy smoke test: read-only checks of a RUNNING deployment (spec 13.2.11).

    python scripts/post_deploy_smoke.py --api https://api.example.com [--frontend https://app.example.com]

It only sends GET requests, creates nothing and logs in nowhere, so it is safe to run against production right after a deploy.
Exit code 0 when every check passed, 1 otherwise. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


def _get(url: str, timeout: float = 30.0) -> tuple[int, bytes, float]:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": "post-deploy-smoke/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - the URL is the operator's own deployment
            return response.status, response.read(2_000_000), time.monotonic() - started
    except urllib.error.HTTPError as error:
        return error.code, error.read(2_000_000), time.monotonic() - started


def check_api(base: str) -> list[Result]:
    results: list[Result] = []
    base = base.rstrip("/")

    status, body, took = _get(f"{base}/health")
    results.append(Result("api /health", status == 200 and b"ok" in body, f"HTTP {status} in {took:.1f}s"))

    status, body, took = _get(f"{base}/health/ready")
    try:
        ready = json.loads(body)
    except ValueError:
        ready = {}
    database = ready.get("database")
    database_ok = database in (True, "ok") or (isinstance(database, dict) and database.get("status") == "ok")
    results.append(Result("api /health/ready answers", status == 200 and bool(ready), f"HTTP {status} in {took:.1f}s"))
    results.append(Result("api reports its database as reachable", database_ok, f"database={database!r}"))

    status, body, _ = _get(f"{base}/openapi.json")
    try:
        paths = len(json.loads(body).get("paths", {}))
    except ValueError:
        paths = 0
    results.append(Result("api publishes its OpenAPI document", status == 200 and paths > 100, f"{paths} paths"))

    status, _, _ = _get(f"{base}/billing/plans")
    results.append(Result("public plans endpoint answers", status == 200, f"HTTP {status}"))

    status, _, _ = _get(f"{base}/organizations")
    results.append(Result("a protected route refuses anonymous calls", status in (401, 403), f"HTTP {status}"))
    return results


def check_frontend(base: str) -> list[Result]:
    base = base.rstrip("/")
    results: list[Result] = []
    for path, needle in (("/", b"<html"), ("/login", b"<html"), ("/register", b"<html")):
        status, body, took = _get(f"{base}{path}")
        results.append(Result(f"frontend {path}", status == 200 and needle in body.lower(), f"HTTP {status} in {took:.1f}s"))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", required=True, help="base URL of the API")
    parser.add_argument("--frontend", help="base URL of the web app (optional)")
    args = parser.parse_args(argv)

    results = check_api(args.api)
    if args.frontend:
        results += check_frontend(args.frontend)
    for result in results:
        print(f"[{'ok' if result.ok else 'FAIL'}] {result.name}: {result.detail}")
    failed = [r for r in results if not r.ok]
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
