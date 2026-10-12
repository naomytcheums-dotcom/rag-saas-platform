"""Refuse to run a script that imports `api.*` when the environment points at a real database or real services.

The test suite has had this protection since 2026-10-10 (tests/_remote_guard.py, tests/conftest.py); scripts did not: `scripts/export_openapi.py` run with the
real `.env` read the production pooler URL on 2026-10-12. Call `require_local_services()` BEFORE the first `import api...` of a script that must never
touch a real service (generators, measurements). Scripts that target a real database on purpose (migrations, staging, the maintenance runner) do not use it:
they are listed with their reason in tests/test_script_guard_contract.py.

Bypass on purpose with ALLOW_REMOTE_TEST_SERVICES=1; paid provider keys are also accepted when RUN_REAL_LLM_TESTS=1.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require_local_services() -> None:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    import _remote_guard
    from api.config import settings

    problems = _remote_guard.find_remote_services(
        {name: getattr(settings, name, "") for name in _remote_guard.GUARDED_SETTINGS},
        allow_paid_keys=os.environ.get("RUN_REAL_LLM_TESTS") == "1",
    )
    if problems and os.environ.get("ALLOW_REMOTE_TEST_SERVICES") != "1":
        raise SystemExit(
            "Refusing to run: " + "; ".join(problems) + ". Point the settings at a disposable local stack and blank the hosted services and paid keys "
            "(for example RAG_ENV_FILE=.no-env), or set ALLOW_REMOTE_TEST_SERVICES=1 if you are sure."
        )
