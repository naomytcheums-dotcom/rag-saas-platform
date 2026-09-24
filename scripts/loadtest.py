"""Real, dependency-light load test for the api/ HTTP layer.

Hits a target URL N times with C concurrent clients, measures real
latency percentiles (p50/p95/p99), and reports throughput. Uses only
`httpx` (already a real project dependency) -- no locust/k6 install
needed for a quick, honest sanity check.

This complements -- does not replace -- Prometheus's own continuous
p50/p95/p99 at GET /metrics (api/monitoring.py): Prometheus measures
whatever the real running server actually sees, this script measures
what a real client actually waits for, on demand, from a chosen
concurrency level.

Usage:
    python scripts/loadtest.py --url http://localhost:8000/health --requests 500 --concurrency 20
    python scripts/loadtest.py --url http://localhost:8000/metrics --requests 200 --concurrency 10
    python scripts/loadtest.py --url http://localhost:8000/health --requests 1000 --concurrency 50 --json

Exit codes:
    0  -- all requests succeeded
    1  -- at least one request failed (the report still prints)
    2  -- a real connection/setup error (server unreachable, bad URL)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time

import httpx


async def _one_request(client: httpx.AsyncClient, url: str, results: list, errors: list) -> None:
    start = time.perf_counter()
    try:
        response = await client.get(url)
        elapsed = time.perf_counter() - start
        if response.status_code >= 400:
            errors.append(f"HTTP {response.status_code}")
        else:
            results.append(elapsed)
    except Exception as exc:  # noqa: BLE001 -- any transport failure is real, reported as an error
        errors.append(str(exc))


async def run_loadtest(url: str, total_requests: int, concurrency: int, timeout: float) -> dict:
    results: list[float] = []
    errors: list[str] = []
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async def bounded():
            async with sem:
                await _one_request(client, url, results, errors)

        wall_start = time.perf_counter()
        await asyncio.gather(*(bounded() for _ in range(total_requests)))
        wall_elapsed = time.perf_counter() - wall_start

    report: dict = {
        "url": url,
        "total_requests": total_requests,
        "concurrency": concurrency,
        "succeeded": len(results),
        "failed": len(errors),
        "wall_seconds": round(wall_elapsed, 3),
        "throughput_rps": round(len(results) / wall_elapsed, 2) if wall_elapsed > 0 else 0.0,
    }
    if results:
        results_sorted = sorted(results)
        def pct(p: float) -> float:
            idx = max(0, min(len(results_sorted) - 1, int(round(p / 100.0 * (len(results_sorted) - 1)))))
            return round(results_sorted[idx] * 1000.0, 2)  # ms
        report.update({
            "min_ms": round(results_sorted[0] * 1000.0, 2),
            "p50_ms": pct(50),
            "p95_ms": pct(95),
            "p99_ms": pct(99),
            "max_ms": round(results_sorted[-1] * 1000.0, 2),
            "mean_ms": round(statistics.mean(results_sorted) * 1000.0, 2),
            "stdev_ms": round(statistics.pstdev(results_sorted) * 1000.0, 2) if len(results_sorted) > 1 else 0.0,
        })
    if errors:
        report["sample_errors"] = errors[:5]

    return report


def _print_report(report: dict) -> None:
    print(f"URL:           {report['url']}")
    print(f"Requests:      {report['total_requests']} (concurrency {report['concurrency']})")
    print(f"Succeeded:     {report['succeeded']}")
    print(f"Failed:        {report['failed']}")
    print(f"Wall time:     {report['wall_seconds']}s")
    print(f"Throughput:    {report['throughput_rps']} req/s")
    if "p50_ms" in report:
        print("Latency (ms):")
        print(f"  min    {report['min_ms']}")
        print(f"  mean   {report['mean_ms']}")
        print(f"  p50    {report['p50_ms']}")
        print(f"  p95    {report['p95_ms']}")
        print(f"  p99    {report['p99_ms']}")
        print(f"  max    {report['max_ms']}")
        print(f"  stdev  {report['stdev_ms']}")
    if "sample_errors" in report:
        print("Sample errors:")
        for err in report["sample_errors"]:
            print(f"  {err}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Real, dependency-light HTTP load test.")
    parser.add_argument("--url", required=True, help="Target URL (e.g. http://localhost:8000/health)")
    parser.add_argument("--requests", type=int, default=500, help="Total number of requests (default 500)")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent clients (default 20)")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout in seconds (default 30)")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON instead of a table")
    args = parser.parse_args()

    if args.requests <= 0 or args.concurrency <= 0:
        print("--requests and --concurrency must be positive integers", file=sys.stderr)
        return 2

    try:
        report = asyncio.run(run_loadtest(args.url, args.requests, args.concurrency, args.timeout))
    except Exception as exc:  # noqa: BLE001 -- setup failure (bad URL, server unreachable)
        print(f"loadtest setup failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report)

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
