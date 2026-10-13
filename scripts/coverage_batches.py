"""Measure the real line coverage of api/ by running the whole backend test suite in memory-bounded batches (spec 13.1.6).

One `coverage run -m pytest <files>` per batch (a single pytest process for the full suite exhausts the RAM of a development machine), every batch writes its own
data file under --out, then the files are combined into one report. Nothing is estimated: the figure printed at the end is `coverage report` over the combined data.

    scripts/coverage_batches.py --out .cov --batch-size 12            # run everything, then report
    scripts/coverage_batches.py --out .cov --report-only              # only combine + report what the batches already measured
    scripts/coverage_batches.py --out .cov --only tests/test_a.py ... # run only some files (appends to the same data directory)

The environment of the isolated local stack (disposable PostgreSQL / Redis, every paid or remote service blanked) must already be exported, for example
`. scripts/test_env/infra_stack_env.sh`; tests/conftest.py refuses to start if anything points to a remote host.
Per-batch result (files, exit code, pytest summary line, seconds) is appended to <out>/batches.jsonl so an interrupted run resumes: batches already recorded are skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# the files CI itself ignores (.github/workflows/ci.yml): they need a real external service or a model download
CI_IGNORED = {
    "tests/test_agent.py", "tests/test_injection_test_set.py", "tests/test_integrations.py", "tests/test_regression.py", "tests/test_voice.py",
}


def discover() -> list[str]:
    files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").rglob("test_*.py"))
    return [f for f in files if f not in CI_IGNORED and "/llm_optin/" not in f]


def done_batches(out: Path) -> set[str]:
    log = out / "batches.jsonl"
    if not log.exists():
        return set()
    return {json.loads(line)["id"] for line in log.read_text(encoding="utf-8").splitlines() if line.strip()}


def run_batch(batch_id: str, files: list[str], out: Path, timeout: int) -> dict:
    data_file = out / f".coverage.{batch_id}"
    cmd = [
        sys.executable, "-m", "coverage", "run", f"--rcfile={ROOT / 'pyproject.toml'}", f"--data-file={data_file}", "--source=api",
        "-m", "pytest", "-p", "no:cacheprovider", "-q", "--maxfail=200", *files,
    ]
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
        code, text = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        code, text = 124, f"timeout after {timeout}s\n{(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout, bytes) else (exc.stdout or '')}"
    summary = next((line for line in reversed(text.splitlines()) if " passed" in line or " failed" in line or " error" in line), text.strip().splitlines()[-1] if text.strip() else "")
    failed = [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR"))]
    (out / f"{batch_id}.log").write_text(text[-20000:], encoding="utf-8")
    return {"id": batch_id, "files": files, "exit": code, "summary": summary.strip(), "failed": failed[:30], "seconds": round(time.time() - started)}


def report(out: Path, fail_under: float | None) -> int:
    rc = ["--rcfile", str(ROOT / "pyproject.toml")]
    parts = sorted(str(p) for p in out.glob(".coverage.*") if not p.name.endswith(".log"))
    if not parts:
        print("no coverage data found in", out)
        return 2
    combined = out / ".coverage"
    subprocess.run([sys.executable, "-m", "coverage", "combine", "--keep", f"--data-file={combined}", *rc, *parts], cwd=ROOT, check=True)
    shown = subprocess.run([sys.executable, "-m", "coverage", "report", f"--data-file={combined}", *rc, "--sort=cover", "--skip-empty", "--include=api/*"], cwd=ROOT, capture_output=True, text=True, check=False)
    (out / "report.txt").write_text(shown.stdout, encoding="utf-8")
    print(shown.stdout[-6000:])
    subprocess.run([sys.executable, "-m", "coverage", "json", f"--data-file={combined}", *rc, "-o", str(out / "coverage.json"), "--include=api/*"], cwd=ROOT, check=False)
    total = json.loads((out / "coverage.json").read_text(encoding="utf-8"))["totals"]
    print(f"TOTAL line coverage of api/: {total['percent_covered']:.2f}% ({total['covered_lines']}/{total['num_statements']} statements, {total['missing_lines']} missing)")
    return 0 if fail_under is None or total["percent_covered"] >= fail_under else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=".cov")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=3600, help="seconds per batch")
    parser.add_argument("--only", nargs="*", help="run only these files, as one extra batch")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--fail-under", type=float, default=None)
    args = parser.parse_args()
    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.report_only:
        if args.only:
            batches = {f"only-{int(time.time())}": args.only}
        else:
            files = discover()
            batches = {f"b{i // args.batch_size:03d}": files[i:i + args.batch_size] for i in range(0, len(files), args.batch_size)}
        finished = done_batches(out)
        for batch_id, files in batches.items():
            if batch_id in finished:
                print(f"skip {batch_id} (already measured)")
                continue
            print(f"run {batch_id}: {len(files)} files", flush=True)
            result = run_batch(batch_id, files, out, args.timeout)
            with (out / "batches.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result) + "\n")
            print(f"  exit {result['exit']} in {result['seconds']}s: {result['summary']}", flush=True)
    return report(out, args.fail_under)


if __name__ == "__main__":
    raise SystemExit(main())
