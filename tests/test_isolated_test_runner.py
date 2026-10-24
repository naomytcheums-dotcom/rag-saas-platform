"""The isolated test runner (scripts/run_isolated_tests.py): it must refuse anything that could reach a real service, and it must never
hand the child process a credential from the parent environment. Pure function tests: no database, Redis or network."""

import pytest

from external_skip_allowlist import EXTERNAL_SKIPS, external_category
from scripts.run_isolated_tests import IsolationRefused, build_test_environment

LOCAL_DB = "postgresql+asyncpg://user:pw@127.0.0.1:15432/rag_test_integration"


def _parent(**overrides):
    parent = {"PATH": "x", "RAG_TEST_DATABASE_URL": LOCAL_DB}
    parent.update(overrides)
    return {k: v for k, v in parent.items() if v is not None}


def test_a_local_throwaway_stack_is_accepted_and_wired_everywhere():
    env = build_test_environment(_parent())
    assert env["DATABASE_URL"] == env["DATABASE_URL_TRANSACTION"] == LOCAL_DB
    assert env["CELERY_BROKER_URL"].startswith("redis://127.0.0.1:") and env["S3_ENDPOINT_URL"].startswith("http://127.0.0.1:")
    assert env["RAG_STRICT_SKIPS"] == "1" and env["COOKIE_SECURE"] == "False"


@pytest.mark.parametrize(
    "overrides",
    [
        {"RAG_TEST_DATABASE_URL": None},
        {"RAG_TEST_DATABASE_URL": "postgresql+asyncpg://u:p@aws-0-eu.pooler.supabase.com:6543/postgres"},
        {"RAG_TEST_DATABASE_URL": "postgresql+asyncpg://u:p@db.internal.example.com:5432/rag_test_integration"},
        {"RAG_TEST_REDIS_URL": "redis://default:pw@eu1-example.upstash.io:6379"},
        {"RAG_TEST_S3_ENDPOINT": "https://example.r2.cloudflarestorage.com"},
    ],
)
def test_anything_that_is_not_local_is_refused_before_the_tests_start(overrides):
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(**overrides))


def test_a_local_database_without_a_throwaway_name_is_refused():
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(RAG_TEST_DATABASE_URL="postgresql+asyncpg://u:p@127.0.0.1:5432/postgres"))


def test_the_parent_environment_never_leaks_into_the_child():
    parent = _parent(
        DATABASE_URL="postgresql+asyncpg://u:p@db.prod.example.com:6543/postgres",
        DATABASE_URL_TRANSACTION="postgresql+asyncpg://u:p@pooler.prod.example.com:6543/postgres",
        STRIPE_SECRET_KEY="sk_live_not_a_real_key",
        PAYSTACK_SECRET_KEY="sk_live_not_a_real_key",
        ANTHROPIC_API_KEY="sk-ant-not-a-real-key",
        SENTRY_DSN="https://key@o0.ingest.sentry.io/1",
    )
    env = build_test_environment(parent)
    for name in ("STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY", "ANTHROPIC_API_KEY", "SENTRY_DSN"):
        assert name not in env
    assert env["DATABASE_URL"] == LOCAL_DB and env["DATABASE_URL_TRANSACTION"] == LOCAL_DB
    assert env["RAG_ENV_FILE"].endswith("does-not-exist")


def test_the_destructive_database_must_be_marked_and_different():
    env = build_test_environment(_parent(RAG_TEST_PG_ROUNDTRIP_URL="postgresql+asyncpg://u:p@127.0.0.1:15432/rag_remediation_scratch"))
    assert env["RAG_DISPOSABLE_PG_CONFIRM"] == "rag_remediation_scratch"
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(RAG_TEST_PG_ROUNDTRIP_URL="postgresql+asyncpg://u:p@127.0.0.1:15432/rag_test_integration"))
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(RAG_TEST_PG_ROUNDTRIP_URL="postgresql+asyncpg://u:p@127.0.0.1:15432/orders"))
    with pytest.raises(IsolationRefused):
        build_test_environment(_parent(RAG_TEST_P0_PG_URL="postgresql+asyncpg://u:p@127.0.0.1:15432/rag_test_integration"))


def test_only_documented_external_dependencies_may_stay_skipped():
    assert external_category("needs a real STRIPE_SECRET_KEY and STRIPE_TEST_PRICE_ID (a real price_id)") == "payment-provider-sandbox"
    assert external_category("Live staging tests require RAG_STAGING_TESTS=YES and the guarded staging runner.") == "hosted-staging"
    for local_reason in (
        "DATABASE_URL is not reachable -- skipping Postgres integration tests",
        "Redis is not reachable at CACHE_REDIS_URL -- skipping cache tests",
        "real Tesseract binary not installed on this machine",
        "PostgreSQL tests not authorized: RAG_DISPOSABLE_PG_URL is not set",
        "No live Celery worker responded to a ping",
        "",
    ):
        assert external_category(local_reason) is None, local_reason
    assert len(EXTERNAL_SKIPS) == 13  # was 5, then 9 (contracts and llm_optin), now four more image/download-heavy suites


def test_the_model_hub_is_only_switched_off_on_request():
    assert "HF_HUB_OFFLINE" not in build_test_environment(_parent())
    env = build_test_environment(_parent(RAG_TEST_HF_OFFLINE="1"))
    assert env["HF_HUB_OFFLINE"] == "1" and env["TRANSFORMERS_OFFLINE"] == "1"
    assert "HF_HUB_OFFLINE" not in build_test_environment(_parent(RAG_TEST_HF_OFFLINE="0"))


def test_the_webhook_capture_skip_reasons_are_documented_external_dependencies():
    import re
    from pathlib import Path

    for name in ("test_billing_stripe_live.py", "test_billing_paystack_live.py"):
        source = (Path(__file__).parent / name).read_text(encoding="utf-8")
        reason = "".join(re.findall(r'"([^"]*)"', re.search(r"_WEBHOOK_SKIP_REASON = \((.*?)\n\)", source, re.DOTALL).group(1)))
        assert external_category(reason) == "payment-provider-sandbox", name

def test_the_opt_in_and_heavy_tooling_skips_of_the_contract_suites_are_documented_not_run_reasons():
    """tests/contracts and tests/llm_optin skip on purpose when a heavy or paid dependency is absent. Strict mode must report them as NOT RUN
    (still SKIPPED, never counted as passed), not as failures of the machine, and must still fail on any other skip reason."""
    documented = {
        "real-LLM tests are opt-in: set RUN_REAL_LLM_TESTS=1": "opt-in-real-llm",
        "real-LLM tests are opt-in: set RUN_REAL_LLM_TESTS=1 and the provider's API key (ANTHROPIC_API_KEY by default)": "opt-in-real-llm",
        "needs Windows SAPI (pywin32), node, Playwright for node and the frontend node_modules": "heavy-local-tooling",
        "docker with the nginx:1.29-alpine image is needed": "heavy-local-tooling",
        "the local Jaeger (OTLP 4318 / query 16686) is not running": "heavy-local-tooling",
    }
    for reason, category in documented.items():
        assert external_category(reason) == category, reason
    assert external_category("DATABASE_URL is not reachable -- skipping RBAC integration tests") is None

def test_the_windows_install_locations_reach_the_child_so_that_git_bash_can_be_found():
    """tests/test_celery_worker_workflow.py looks for Git for Windows' bash under %ProgramFiles% when git is not on PATH. Those variables are path
    plumbing, not credentials: the sanitized child must receive them (all ten workflow checks failed in the isolated runner without them)."""
    parent = _parent(**{"ProgramFiles": r"C:\Program Files", "ProgramFiles(x86)": r"C:\Program Files (x86)", "ProgramW6432": r"C:\Program Files"})
    env = build_test_environment(parent)
    for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        assert env[name] == parent[name], name

def test_the_placeholder_sender_address_is_accepted_by_the_applications_own_email_validation():
    """The runner used `...@isolated-tests.invalid`: the e-mail validator rejects special-use TLDs such as `.invalid`, so tests that post the platform's
    default sender (tests/test_domains_email_postgres.py) got a 422 instead of their expected 400. No message is ever sent (no Resend key)."""
    from email_validator import validate_email

    env = build_test_environment(_parent())
    for name in ("EMAIL_FROM_ADDRESS", "SUPPORT_EMAIL"):
        validate_email(env[name], check_deliverability=False)

def test_local_opt_in_suites_are_switched_on_only_by_name_from_a_closed_list():
    """Two opt-in suites can run on this stack (PostgreSQL + pgvector, and the prompt-injection model already in the local Hugging Face cache).
    RAG_TEST_OPT_IN names them; each becomes NAME=1 in the child. Nothing else is accepted: no free-form variable can ride along."""
    assert "PGVECTOR_REAL_TEST" not in build_test_environment(_parent())
    env = build_test_environment(_parent(RAG_TEST_OPT_IN="PGVECTOR_REAL_TEST, PROMPT_INJECTION_MEASURE"))
    assert env["PGVECTOR_REAL_TEST"] == "1" and env["PROMPT_INJECTION_MEASURE"] == "1"
    for forbidden in ("STRIPE_SECRET_KEY", "RUN_REAL_LLM_TESTS", "PGVECTOR_REAL_TEST=0", "anything"):
        with pytest.raises(IsolationRefused):
            build_test_environment(_parent(RAG_TEST_OPT_IN=forbidden))

def test_the_image_and_download_heavy_suites_are_documented_not_run_reasons():
    """ClamAV daemon, Terraform/Helm tooling, the dedicated-tenant stacks and a Jaeger collector each need a Docker image or a download that this
    machine makes at about 0.1 MB/s. They stay SKIPPED (never counted as passed); strict mode must not call them failures of the machine."""
    for reason in (
        "CLAMAV_REAL_TEST_HOST is not set (no real clamd to talk to)",
        "set RUN_DEPLOY_TOOLING=1 (needs Docker and the network)",
        "set RUN_DEPLOY_E2E=1 (needs Docker and a built image)",
        "OTEL_REAL_TEST_JAEGER is not set (no real collector to export to)",
    ):
        assert external_category(reason) == "heavy-local-tooling", reason
