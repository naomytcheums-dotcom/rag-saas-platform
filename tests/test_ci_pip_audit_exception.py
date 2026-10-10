"""pip-audit exception for diskcache (PYSEC-2026-2447 / CVE-2025-69872): it must stay narrow, explained and removable.

diskcache 5.6.3 is the LAST release and has no fixed version. It is not a direct dependency: dspy (requirements-optional.txt, used only by
api/services/prompt_optimization.py) pulls it in for its on-disk LLM cache. Exploitation needs write access to that cache directory.
These tests keep the exception from growing silently and tell whoever drops dspy to drop the exception too.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VULN = "PYSEC-2026-2447"


def _audit_step():
    lines = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").splitlines()
    index = next(i for i, line in enumerate(lines) if line.strip() == "- name: pip-audit")
    run_line = next(line for line in lines[index:index + 12] if "pip-audit" in line and "run:" in line)
    comments = [line.strip() for line in lines[max(0, index - 12):index] if line.strip().startswith("#")]
    return run_line, "\n".join(comments)


def test_the_ci_ignores_exactly_the_diskcache_advisory():
    run_line, _ = _audit_step()
    assert re.findall(r"--ignore-vuln\s+(\S+)", run_line) == [VULN], "only PYSEC-2026-2447 may be ignored, nothing else"
    assert "-r requirements-api.txt" in run_line and "-r requirements-optional.txt" in run_line, "both requirement files must still be audited"


def test_the_exception_is_explained_where_it_lives():
    _, comments = _audit_step()
    for needle in (VULN, "diskcache", "dspy", "prompt_optimization.py", "no fixed"):
        assert needle in comments, f"the comment above the pip-audit step must mention {needle!r}"


def test_the_exception_goes_away_with_its_only_cause():
    optional = (ROOT / "requirements-optional.txt").read_text(encoding="utf-8")
    assert re.search(r"^dspy==", optional, re.MULTILINE), "dspy is gone: remove the PYSEC-2026-2447 exception from .github/workflows/ci.yml"
    assert "diskcache" not in (ROOT / "requirements-api.txt").read_text(encoding="utf-8"), "diskcache became a direct dependency: reassess the exception"
