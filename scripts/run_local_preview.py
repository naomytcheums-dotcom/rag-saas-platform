"""Start the API for a LOCAL interface preview without ever reaching a real service.

    RAG_PREVIEW_DATABASE_URL=postgresql+asyncpg://user:pw@127.0.0.1:15432/rag_preview python scripts/run_local_preview.py [--port 8000] [--check]

What it does (and why): the previous preview ran `uvicorn api.main:app` in a shell that inherited the real `.env`, whose
DATABASE_URL_TRANSACTION pointed at the hosted pooler. Here the child process gets a SANITIZED environment built from a short
allow-list (never the parent's DATABASE_URL*, REDIS*, STRIPE*, ... and never `.env`: RAG_ENV_FILE points at a file that does not
exist), a local throwaway database that you must name explicitly, in-memory Celery, random ephemeral signing secrets and no
external-service credential. api/config.py then re-checks everything (RAG_RUN_MODE=preview) and refuses to start otherwise.
Nothing printed contains a secret or a connection string.

The database must already have its schema (python -m alembic upgrade head, run by you against that LOCAL database)."""

import argparse
import os
import secrets
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.security.runtime_guard import preview_refusals  # noqa: E402

# Variables the child may inherit: process plumbing only. Nothing that names a service.
INHERITED = ("PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LOCALAPPDATA",
             "APPDATA", "PROGRAMDATA", "LANG", "LC_ALL", "PYTHONIOENCODING", "VIRTUAL_ENV")


def build_preview_environment(parent: Mapping[str, str], database_url: str) -> dict[str, str]:
    env = {name: parent[name] for name in INHERITED if name in parent}
    env.update({
        "RAG_RUN_MODE": "preview",
        "RAG_ENV_FILE": ".env.preview.does-not-exist",
        "PYTHONDONTWRITEBYTECODE": "1",
        "DATABASE_URL": database_url,
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
        "COOKIE_SECURE": "False",
        "SUPPORT_EMAIL": "support@preview.invalid",
        "JWT_SECRET_KEY": secrets.token_urlsafe(48),
        "SESSION_MIDDLEWARE_SECRET": secrets.token_urlsafe(48),
        "AUDIT_LOG_HMAC_SECRET_KEY": secrets.token_urlsafe(48),
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    })
    return env


def main(argv: list[str] | None = None, parent: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check", action="store_true", help="validate the isolation and exit without starting the server")
    args = parser.parse_args(argv)
    parent = os.environ if parent is None else parent

    database_url = (parent.get("RAG_PREVIEW_DATABASE_URL") or "").strip()
    if not database_url:
        print("refused: set RAG_PREVIEW_DATABASE_URL to a LOCAL throwaway PostgreSQL database (127.0.0.1, name containing preview/test/scratch/...).", file=sys.stderr)
        return 2
    env = build_preview_environment(parent, database_url)
    problems = preview_refusals(env)
    if problems:
        print("refused:", *problems, sep="\n  - ", file=sys.stderr)
        return 2
    print("preview isolation check passed (local database, in-memory Celery, no external credential, .env not loaded).")
    if args.check:
        return 0
    command = [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(args.port)]
    return subprocess.call(command, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
