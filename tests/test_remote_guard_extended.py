"""Hardening of the guard that keeps tests and scripts away from real databases and services (phase 2 of the 2026-10-12 security audit).

Found on 2026-10-12: the guard only knew URLs and three keys, so a tunnel to the real database on a local port, a hosted tracing endpoint, a paid LLM key
or a script run with the real `.env` all got through (a span reached the production Tempo, two real Anthropic calls were made, a script read the production pooler URL).
"""

import importlib.util
import re
from pathlib import Path

import pytest

import _remote_guard
from _remote_guard import find_remote_services

ROOT = Path(__file__).resolve().parents[1]


def test_a_local_database_with_a_real_looking_name_is_refused_but_disposable_names_pass():
    refused = find_remote_services({"DATABASE_URL": "postgresql+asyncpg://postgres:s3cret-pw@127.0.0.1:5433/postgres"})
    assert len(refused) == 1 and "DATABASE_URL" in refused[0] and "disposable" in refused[0]
    assert "s3cret" not in refused[0]  # the message never echoes the password
    for name in ("rag_saas_test", "pytest_p0", "rag_test_roundtrip_scratch", "tmp_run"):
        assert find_remote_services({"DATABASE_URL": f"postgresql+asyncpg://postgres:pw@localhost:5432/{name}"}) == []
    assert find_remote_services({"DATABASE_URL": "sqlite+aiosqlite:///:memory:"}) == []


def test_the_transaction_pooler_url_is_held_to_the_same_rule():
    problems = find_remote_services({"DATABASE_URL_TRANSACTION": "postgresql://u:pw@localhost:6543/postgres"})
    assert len(problems) == 1 and "DATABASE_URL_TRANSACTION" in problems[0]


@pytest.mark.parametrize("name,value", [
    ("TEMPO_HOST", "tempo-prod-eu-west-0.grafana.net"),
    ("LOKI_HOST", "https://logs-prod-012.grafana.net"),
    ("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    ("SENTRY_DSN", "https://abc123@o123456.ingest.sentry.io/789"),
    ("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp-gateway.example.net/otlp"),
    ("SECURITY_ALERT_WEBHOOK_URL", "https://hooks.slack.com/services/T0/B0/xyz"),
])
def test_hosted_observability_and_alert_endpoints_are_refused(name, value):
    problems = find_remote_services({name: value})
    assert len(problems) == 1 and name in problems[0]


def test_local_or_empty_observability_endpoints_pass():
    assert find_remote_services({"OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4318", "TEMPO_HOST": "localhost:3200", "LOKI_HOST": "", "SENTRY_DSN": None}) == []


@pytest.mark.parametrize("name", list(_remote_guard.PAID_KEY_SETTINGS))
def test_a_paid_provider_key_is_refused_unless_the_real_llm_run_is_opted_in(name):
    key = "sk-live-0123456789abcdef"
    problems = find_remote_services({name: key})
    assert len(problems) == 1 and name in problems[0]
    assert key not in problems[0]  # never echoes the key
    assert find_remote_services({name: key}, allow_paid_keys=True) == []
    assert find_remote_services({name: "ci-only-placeholder"}) == []
    assert find_remote_services({name: ""}) == []


def test_conftest_passes_every_guarded_setting_and_the_real_llm_opt_in_to_the_guard():
    text = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "_remote_guard.GUARDED_SETTINGS" in text
    assert 'allow_paid_keys=_os.environ.get("RUN_REAL_LLM_TESTS") == "1"' in text


def test_the_local_test_runner_blanks_everything_the_guard_would_refuse():
    script = (ROOT / "scripts" / "run_tests_local.sh").read_text(encoding="utf-8")
    for name in (*_remote_guard.OBSERVABILITY_SETTINGS, *_remote_guard.PAID_KEY_SETTINGS):
        assert f'{name}=""' in script, f"scripts/run_tests_local.sh must blank {name}, otherwise the runner would be refused by its own guard"


def _load_script_guard():
    spec = importlib.util.spec_from_file_location("local_only_guard", ROOT / "scripts" / "local_only_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_script_is_refused_when_the_settings_point_at_a_real_service(monkeypatch):
    from api.config import settings

    guard = _load_script_guard()
    monkeypatch.delenv("ALLOW_REMOTE_TEST_SERVICES", raising=False)
    monkeypatch.setattr(settings, "DATABASE_URL_TRANSACTION", "postgresql://u:pw-secret@aws-0-eu.pooler.supabase.com:6543/postgres")
    with pytest.raises(SystemExit) as refused:
        guard.require_local_services()
    message = str(refused.value)
    assert "DATABASE_URL_TRANSACTION" in message and "pw-secret" not in message
    monkeypatch.setenv("ALLOW_REMOTE_TEST_SERVICES", "1")
    guard.require_local_services()  # the explicit bypass still works


def test_a_script_run_on_a_disposable_local_stack_is_accepted(monkeypatch):
    from api.config import settings

    guard = _load_script_guard()
    monkeypatch.delenv("ALLOW_REMOTE_TEST_SERVICES", raising=False)
    for name in (*_remote_guard.OBSERVABILITY_SETTINGS, *_remote_guard.PAID_KEY_SETTINGS, "DATABASE_URL_TRANSACTION"):
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://postgres:pw@127.0.0.1:25432/pytest_p0")
    guard.require_local_services()


# Scripts that import `api.*` and may therefore open a database or call a service. Either they call require_local_services() before the first
# api import, or they are listed here with the reason they are allowed to target something else (a new script must be classified on purpose).
SCRIPTS_THAT_TARGET_SOMETHING_ELSE = {
    "audit_inventory.py": "builds its own isolated environment (static inventory, no connection)",
    "check_optional_deps.py": "builds its own isolated environment (import check, no connection)",
    "dev_isolated_server.py": "refuses to start unless everything is local (its own check, throw-away SQLite)",
    "retrieval_benchmark.py": "portable path on a temporary SQLite file",
    "retrieval_benchmark_pg.py": "has its own target rules (staging database by default, --allow-main plus emptiness check)",
    "run_isolated_tests.py": "is itself the guard: refuses any non-local database, Redis or S3 and runs pytest in a sanitized environment that never inherits .env",
    "run_local_preview.py": "is itself the guard: builds a sanitized allow-listed environment for a local throwaway database and refuses to start otherwise (RAG_RUN_MODE=preview)",
    "scrub_system_logs.py": "cleans the database the owner points it at, on purpose: dry run by default, --apply needs the exact database name",
    "validate_paystack_live.py": "opt-in live check of the vendor sandbox (RUN_LIVE_VENDOR_VALIDATION=1, test key only, refuses live keys); opens no database",
    "staging_journeys.py": "live journeys against staging by design (--execute and .env.staging)",
}
_API_IMPORT = re.compile(r"^\s*(?:from|import) api(?:\.|\s)", re.MULTILINE)


def _scripts_importing_api():
    return sorted(p for p in (ROOT / "scripts").glob("*.py") if _API_IMPORT.search(p.read_text(encoding="utf-8")))


def test_every_script_importing_the_application_is_guarded_or_explicitly_classified():
    unclassified = []
    for path in _scripts_importing_api():
        text = path.read_text(encoding="utf-8")
        if path.name in SCRIPTS_THAT_TARGET_SOMETHING_ELSE:
            continue
        guard_at = text.find("require_local_services()")
        first_import = _API_IMPORT.search(text)
        if guard_at == -1 or guard_at > first_import.start():
            unclassified.append(path.name)
    assert not unclassified, f"call scripts/local_only_guard.require_local_services() before the first api import, or classify the script on purpose: {unclassified}"


def test_the_classification_list_has_no_stale_entries():
    importing = {p.name for p in _scripts_importing_api()}
    assert set(SCRIPTS_THAT_TARGET_SOMETHING_ELSE) <= importing, set(SCRIPTS_THAT_TARGET_SOMETHING_ELSE) - importing
