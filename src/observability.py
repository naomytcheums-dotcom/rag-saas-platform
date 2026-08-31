"""
Phase 05: structured, per-request telemetry -- cost, latency, and tool
usage, logged locally as newline-delimited JSON. Cheap enough to query
with plain Python and no new service to run, but shaped so a later swap
to Grafana/Prometheus (mentioned as a "later" option in the architecture
plan from the start) is a storage-layer change, not a redesign: one flat
record per request, one metric per field, nothing that only makes sense
inside this file's own aggregation functions.

record_run() is a thin wrapper around Agent.run(), not a change to the
agent itself -- observability stays opt-in at the call site instead of
hardwired into the agent's own logic, and it re-raises whatever the
agent raised so the caller still sees the real error.
"""

import json
import math
import time
from collections import Counter
from pathlib import Path

from generation import estimate_cost_usd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TELEMETRY_PATH = PROJECT_ROOT / "data" / "telemetry.jsonl"


class TelemetryStore:
    def __init__(self, path=DEFAULT_TELEMETRY_PATH):
        self.path = Path(path)

    def append(self, record):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def read_all(self):
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


def record_run(store, agent, question):
    start = time.perf_counter()
    try:
        outcome = agent.run(question)
    except RuntimeError as exc:
        # The run failed before producing token counts -- logged as a
        # zero-cost, zero-tool failure rather than guessed at. Real cost
        # was likely spent on the failed attempts too; not captured here,
        # a known gap rather than an invented number.
        store.append({
            "question": question,
            "success": False,
            "error": str(exc),
            "tools_used": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "elapsed_ms": round((time.perf_counter() - start) * 1000),
        })
        raise

    store.append({
        "question": question,
        "success": True,
        "error": None,
        "tools_used": outcome["tools_used"],
        "input_tokens": outcome["input_tokens"],
        "output_tokens": outcome["output_tokens"],
        "cost_usd": estimate_cost_usd(outcome["input_tokens"], outcome["output_tokens"]),
        "elapsed_ms": outcome["elapsed_ms"],
    })
    return outcome


def _percentile(values, p):
    """Nearest-rank percentile, the usual definition for latency
    percentiles (p50/p95) in observability tooling: sort the samples and
    take the value at rank ceil(p/100 * n), not an interpolated average
    between two samples."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def latency_summary(records):
    latencies = [r["elapsed_ms"] for r in records]
    return {
        "count": len(records),
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
    }


def total_cost_usd(records):
    return sum(r["cost_usd"] for r in records)


def error_rate(records):
    if not records:
        return 0.0
    return sum(1 for r in records if not r["success"]) / len(records)


def tool_usage_counts(records):
    counts = Counter()
    for r in records:
        counts.update(r["tools_used"])
    return dict(counts)


def main():
    store = TelemetryStore()
    records = store.read_all()
    if not records:
        print("No telemetry recorded yet -- calls made through record_run() land in "
              f"{store.path}.")
        return

    latency = latency_summary(records)
    print(f"\n{latency['count']} requests logged")
    print(f"  p50 latency : {latency['p50_ms']}ms")
    print(f"  p95 latency : {latency['p95_ms']}ms")
    print(f"  total cost  : ${total_cost_usd(records):.4f}")
    print(f"  error rate  : {error_rate(records):.0%}")
    print("  tool usage:")
    for tool, count in sorted(tool_usage_counts(records).items(), key=lambda kv: -kv[1]):
        print(f"    {tool}: {count}")


if __name__ == "__main__":
    main()
