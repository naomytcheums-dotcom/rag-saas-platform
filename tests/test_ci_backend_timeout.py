"""The backend-tests job must be able to finish the suite and must name its failures.

Observed on GitHub Actions (PR #20 and main alike): the job is cancelled by its 30-minute limit with pytest still running, at about 61 %
of the suite after 27 minutes (so roughly 45 minutes in total on a standard runner). A job that never finishes can never be green, and
with `-q` and no `-r` option a failure shows up only as an F in a progress line until the very end. The limit must leave headroom over
the measured duration, and the run must print a short summary of failed and errored tests.
"""

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _backend_tests_block() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("  backend-tests:")
    end = text.index("\n  backend-security:", start)
    return text[start:end]


def test_the_job_limit_leaves_headroom_over_the_measured_duration():
    limit = int(re.search(r"^\s+timeout-minutes:\s*(\d+)\s*$", _backend_tests_block(), re.MULTILINE).group(1))
    assert limit >= 60, f"timeout-minutes is {limit}: the suite needs about 45 minutes on a standard GitHub runner"


def test_the_run_prints_a_summary_of_failed_and_errored_tests():
    command = next(line for line in _backend_tests_block().splitlines() if line.strip().startswith("run: pytest"))
    assert re.search(r"\s-rfE\b", command), "pytest must be run with -rfE so the failures are listed by name"
    assert "--maxfail=20" in command, "the failure ceiling must stay"
    for ignored in ("tests/test_voice.py", "tests/test_agent.py", "tests_pipeline/test_retrieval.py"):
        assert f"--ignore={ignored}" in command, f"the established exclusion {ignored} must stay"
