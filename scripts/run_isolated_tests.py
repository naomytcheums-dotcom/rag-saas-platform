"""Run pytest against a LOCAL, throwaway stack (PostgreSQL, Redis, S3-compatible storage) and nothing else.

    python scripts/run_isolated_tests.py [--check] [--flush-redis] [--with-worker] -- <pytest arguments>

Inputs (environment of the caller, every one mandatory unless a default is shown):
    RAG_TEST_DATABASE_URL  postgresql+asyncpg://...@127.0.0.1:<port>/<database containing test|disposable|scratch|...>, already migrated
    RAG_TEST_REDIS_URL     redis://127.0.0.1:<port>                      (default redis://127.0.0.1:16379)
    RAG_TEST_S3_ENDPOINT   http://127.0.0.1:<port>  MinIO with the avatars/documents/voice buckets (default http://127.0.0.1:19000)
    RAG_TEST_PG_ROUNDTRIP_URL  optional: a second local database whose name contains disposable|roundtrip|scratch|throwaway, for the
                           destructive concurrency and RLS tests (needs no confirmation variable: the runner sets it to the database name)

The child process gets a SANITIZED environment (same idea as run_local_preview.py): only process plumbing is inherited, `.env` is never
loaded, every setting that could point at a real service is replaced, and the result is checked with api.security.runtime_guard before
pytest starts. It fails loudly when a dependency is missing: nothing is converted into a skipped test.
Nothing printed contains a secret or a connection string."""

import argparse
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.security.runtime_guard import LOCAL_HOSTS, preview_refusals  # noqa: E402

INHERITED = ("PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LOCALAPPDATA",
             "APPDATA", "PROGRAMDATA", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LANG", "LC_ALL", "PYTHONIOENCODING", "VIRTUAL_ENV")
# Placeholders that CI already uses (".circleci/config.yml"): they make the OAuth clients register, they open nothing.
PLACEHOLDER = re.compile(r"(never[-_]?(a[-_])?real|placeholder)", re.IGNORECASE)
ROUNDTRIP_MARKER = re.compile(r"(disposable|roundtrip|scratch|throwaway)", re.IGNORECASE)


class IsolationRefused(ValueError):
    pass


def _local(url: str, what: str) -> tuple[str, int, str]:
    parsed = urlparse(url.replace("+asyncpg", "").replace("+psycopg2", ""))
    host = (parsed.hostname or "").lower()
    if host not in LOCAL_HOSTS:
        raise IsolationRefused(f"{what} is not a local address (127.0.0.1, localhost or ::1 only)")
    return host, parsed.port or 0, parsed.path.lstrip("/")


def build_test_environment(parent: Mapping[str, str]) -> dict[str, str]:
    """Sanitized environment for the child pytest. Raises IsolationRefused naming the setting (never its value)."""
    database = (parent.get("RAG_TEST_DATABASE_URL") or "").strip()
    if not database:
        raise IsolationRefused("RAG_TEST_DATABASE_URL is not set")
    _local(database, "RAG_TEST_DATABASE_URL")
    redis = (parent.get("RAG_TEST_REDIS_URL") or "redis://127.0.0.1:16379").strip().rstrip("/")
    _local(redis, "RAG_TEST_REDIS_URL")
    s3 = (parent.get("RAG_TEST_S3_ENDPOINT") or "http://127.0.0.1:19000").strip().rstrip("/")
    _local(s3, "RAG_TEST_S3_ENDPOINT")

    from cryptography.fernet import Fernet

    env = {name: parent[name] for name in INHERITED if name in parent}
    extra_dirs = [d for d in (parent.get("RAG_TEST_EXTRA_PATH") or "").split(os.pathsep) if d]
    missing_dirs = [d for d in extra_dirs if not Path(d).is_dir()]
    if missing_dirs:
        raise IsolationRefused("RAG_TEST_EXTRA_PATH lists a directory that does not exist")
    if extra_dirs:
        env["PATH"] = os.pathsep.join([*extra_dirs, env.get("PATH", "")])
    tessdata = (parent.get("RAG_TEST_TESSDATA") or "").strip()
    if (parent.get("RAG_TEST_HF_OFFLINE") or "").strip() == "1":
        # Models already in the local cache are loaded without any request to the hub: no network, no shared HTTP client state. A model
        # that is NOT cached then fails loudly instead of being downloaded during a test.
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
    if tessdata:
        if not Path(tessdata).is_dir():
            raise IsolationRefused("RAG_TEST_TESSDATA is not an existing directory")
        env["TESSDATA_PREFIX"] = tessdata
    env.update({
        "RAG_ENV_FILE": ".env.isolated-tests.does-not-exist",
        "PYTHONDONTWRITEBYTECODE": "1",
        "RAG_STRICT_SKIPS": "1",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "DATABASE_URL": database,
        "DATABASE_URL_TRANSACTION": database,
        "CELERY_BROKER_URL": f"{redis}/0",
        "CELERY_RESULT_BACKEND": f"{redis}/1",
        "RATE_LIMIT_REDIS_URL": f"{redis}/2",
        "CACHE_REDIS_URL": f"{redis}/3",
        "RATE_LIMIT_ENABLED": "True",
        "S3_ENDPOINT_URL": s3,
        "S3_BUCKET_NAME": "avatars",
        "S3_ACCESS_KEY_ID": "minioadmin",
        "S3_SECRET_ACCESS_KEY": "minioadmin",
        "S3_REGION": "us-east-1",
        "S3_PUBLIC_BASE_URL": f"{s3}/public/avatars",
        "S3_DOCUMENTS_BUCKET_NAME": "documents",
        "S3_VOICE_BUCKET_NAME": "voice",
        "COOKIE_SECURE": "False",
        "SUPPORT_EMAIL": "support@isolated-tests.invalid",
        "EMAIL_FROM_ADDRESS": "onboarding@isolated-tests.invalid",
        "RESEND_API_KEY": "re_placeholder_never_a_real_key",
        "GOOGLE_OAUTH_CLIENT_ID": "ci-only-google-client-id-never-real",
        "GOOGLE_OAUTH_CLIENT_SECRET": "ci-only-google-client-secret-never-real",
        "GITHUB_OAUTH_CLIENT_ID": "ci-only-github-client-id-never-real",
        "GITHUB_OAUTH_CLIENT_SECRET": "ci-only-github-client-secret-never-real",
        "JWT_SECRET_KEY": secrets.token_urlsafe(48),
        "SESSION_MIDDLEWARE_SECRET": secrets.token_urlsafe(48),
        "AUDIT_LOG_HMAC_SECRET_KEY": secrets.token_urlsafe(48),
        "ENCRYPTION_MASTER_KEY": Fernet.generate_key().decode(),
        "SECRET_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    })
    roundtrip = (parent.get("RAG_TEST_PG_ROUNDTRIP_URL") or "").strip()
    if roundtrip:
        _host, _port, name = _local(roundtrip, "RAG_TEST_PG_ROUNDTRIP_URL")
        if not ROUNDTRIP_MARKER.search(name):
            raise IsolationRefused("RAG_TEST_PG_ROUNDTRIP_URL: the database name must contain disposable, roundtrip, scratch or throwaway")
        if _local(roundtrip, "RAG_TEST_PG_ROUNDTRIP_URL") == _local(database, "RAG_TEST_DATABASE_URL"):
            raise IsolationRefused("RAG_TEST_PG_ROUNDTRIP_URL must differ from RAG_TEST_DATABASE_URL")
        env["RAG_DISPOSABLE_PG_URL"] = roundtrip
        env["RAG_DISPOSABLE_PG_CONFIRM"] = name
    p0 = (parent.get("RAG_TEST_P0_PG_URL") or "").strip()
    if p0:
        _host, _port, p0_name = _local(p0, "RAG_TEST_P0_PG_URL")
        if not p0_name.startswith("pytest_"):
            raise IsolationRefused("RAG_TEST_P0_PG_URL: the database name must start with pytest_")
        env["P0_PG_TEST_URL"] = p0
    # The guard is applied to the final environment; the CI placeholders are allowed because they open nothing.
    checked = {k: ("" if PLACEHOLDER.search(v) else v) for k, v in env.items()}
    problems = preview_refusals(checked)
    if problems:
        raise IsolationRefused("; ".join(problems))
    return env


def _reachable(url: str, default_port: int) -> bool:
    parsed = urlparse(url.replace("+asyncpg", ""))
    try:
        with socket.create_connection((parsed.hostname, parsed.port or default_port), timeout=3):
            return True
    except OSError:
        return False


def check_dependencies(env: Mapping[str, str]) -> list[str]:
    missing = []
    for name, default_port in (("DATABASE_URL", 5432), ("CELERY_BROKER_URL", 6379), ("S3_ENDPOINT_URL", 9000)):
        if not _reachable(env[name], default_port):
            missing.append(f"{name} target is not reachable")
    return missing


def main(argv: list[str] | None = None, parent: Mapping[str, str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    pytest_args: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, pytest_args = argv[:split], argv[split + 1:]
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="validate the isolation and the dependencies, then exit")
    parser.add_argument("--flush-redis", action="store_true", help="empty the local throwaway Redis first (rate-limit counters from a previous run)")
    parser.add_argument("--with-worker", action="store_true", help="start a live Celery worker on the throwaway broker for the duration of the run")
    args, extra = parser.parse_known_args(argv)
    pytest_args = [*extra, *pytest_args]
    parent = os.environ if parent is None else parent
    try:
        env = build_test_environment(parent)
    except IsolationRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    missing = check_dependencies(env)
    if missing:
        print("missing dependency (the run stops instead of skipping tests):", *missing, sep="\n  - ", file=sys.stderr)
        return 3
    print("isolation check passed: local PostgreSQL, Redis and S3, no external credential, .env not loaded.")
    if args.check:
        return 0
    if args.flush_redis:
        import redis

        redis.Redis.from_url(env["CELERY_BROKER_URL"]).flushall()
    worker = None
    if args.with_worker:
        log_path = Path(env.get("TEMP", ".")) / "isolated-tests-celery-worker.log"
        log_file = log_path.open("w", encoding="utf-8")
        worker = subprocess.Popen([sys.executable, "-m", "celery", "-A", "api.tasks.celery_app", "worker", "-P", "solo", "--loglevel=warning"],
                                  cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT)
        answered = False
        for _attempt in range(12):
            time.sleep(10)
            if worker.poll() is not None:
                break
            ping = subprocess.run([sys.executable, "-m", "celery", "-A", "api.tasks.celery_app", "inspect", "ping", "--timeout", "8"], cwd=ROOT, env=env,
                                  capture_output=True, text=True)
            if "pong" in ping.stdout:
                answered = True
                break
        if not answered:
            worker.terminate()
            print(f"the Celery worker did not answer a ping: the run stops (worker log: {log_path}).", file=sys.stderr)
            return 3
        print("live Celery worker answered a ping.")
    try:
        return subprocess.call([sys.executable, "-m", "pytest", *pytest_args], cwd=ROOT, env=env)
    finally:
        if worker is not None:
            worker.terminate()
            worker.wait(timeout=30)


if __name__ == "__main__":
    raise SystemExit(main())
