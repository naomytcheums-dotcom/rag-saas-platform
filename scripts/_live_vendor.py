"""Shared plumbing of the scripts/validate_*_live.py scripts: the ONE-COMMAND real validation of an external vendor integration.

Rules every live script follows:
- it does nothing unless RUN_LIVE_VENDOR_VALIDATION=1 is set explicitly (it spends a few cents at most, and says what before it does);
- keys come ONLY from the process environment; the project's .env is never read (RAG_ENV_FILE is pointed at a file that does not exist) and no key is printed;
- it exercises the PRODUCT's own adapter (the code the application runs), not a second client, so a pass means the product works with that account;
- a vendor with no key in the environment is reported as `skipped`, never as a pass;
- the exit code is 0 only if every requested vendor passed.
The application is imported lazily (importlib) because the settings object needs placeholders for the unrelated mandatory secrets.
"""

import importlib
import json
import os
import secrets
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require_opt_in(what: str, cost: str) -> None:
    if os.environ.get("RUN_LIVE_VENDOR_VALIDATION") != "1":
        print(f"This script calls REAL external services ({what}). Expected cost: {cost}.\nRe-run with RUN_LIVE_VENDOR_VALIDATION=1 to proceed.", file=sys.stderr)
        raise SystemExit(2)


def prepare_product_settings() -> None:
    """Settings the application insists on but these scripts never use (no database connection is ever opened) get throw-away values."""
    os.environ["RAG_ENV_FILE"] = ".no-env"
    from cryptography.fernet import Fernet

    placeholders = {
        "DATABASE_URL": "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/live_validation_unused",
        "JWT_SECRET_KEY": secrets.token_urlsafe(32), "SESSION_MIDDLEWARE_SECRET": secrets.token_urlsafe(32),
        "AUDIT_LOG_HMAC_SECRET_KEY": secrets.token_urlsafe(32), "SUPPORT_EMAIL": "support@example.test",
        "ENCRYPTION_MASTER_KEY": Fernet.generate_key().decode(), "SECRET_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    }
    for name, value in placeholders.items():
        os.environ.setdefault(name, value)
    sys.path.insert(0, str(ROOT))


def product(module: str):
    prepare_product_settings()
    return importlib.import_module(module)


def have(*names: str) -> bool:
    return all(os.environ.get(name) for name in names)


class Report:
    def __init__(self, area: str):
        self.area, self.rows = area, []

    def skipped(self, name: str, reason: str) -> None:
        self.rows.append({"vendor": name, "status": "skipped", "reason": reason})

    async def check(self, name: str, coroutine_factory) -> None:
        started = time.monotonic()
        try:
            detail = await coroutine_factory()
            self.rows.append({"vendor": name, "status": "passed", "seconds": round(time.monotonic() - started, 2), **(detail or {})})
        except Exception as exc:  # noqa: BLE001 -- a validation script reports every failure kind
            self.rows.append({"vendor": name, "status": "FAILED", "seconds": round(time.monotonic() - started, 2), "error": f"{type(exc).__name__}: {str(exc)[:300]}"})

    def finish(self) -> int:
        print(json.dumps({"area": self.area, "results": self.rows}, indent=2))
        failed = [r for r in self.rows if r["status"] == "FAILED"]
        passed = [r for r in self.rows if r["status"] == "passed"]
        if failed or not passed:
            return 1
        return 0
