"""Local preview isolation (RAG_RUN_MODE=preview): a preview can never reach a hosted database, Redis, S3 or an external service.
Origin: a preview once ran with the real .env and created test accounts in the hosted database. Every refusal must name the setting
and the rule but NEVER echo a value (a secret or a connection string must not reach a log)."""

import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.config import Settings
from api.security.runtime_guard import PreviewRefused, assert_preview_is_isolated, is_preview, preview_refusals

SENTINEL = "sentinel-credential-9f3a7c"
HOSTED_DB = f"postgresql+asyncpg://prod_user:{SENTINEL}@db.hosted-provider.example:6543/postgres"
LOCAL_DB = "postgresql+asyncpg://postgres:pw@127.0.0.1:15432/rag_preview"

_spec = importlib.util.spec_from_file_location("run_local_preview", Path(__file__).resolve().parent.parent / "scripts" / "run_local_preview.py")
launcher = importlib.util.module_from_spec(_spec)
sys.modules["run_local_preview"] = launcher
_spec.loader.exec_module(launcher)


def _ok(**overrides):
    env = {"DATABASE_URL": LOCAL_DB, "CELERY_BROKER_URL": "memory://", "CELERY_RESULT_BACKEND": "cache+memory://"}
    env.update(overrides)
    return env


def test_a_local_throwaway_setup_is_accepted():
    assert preview_refusals(_ok()) == []
    assert preview_refusals(_ok(RATE_LIMIT_REDIS_URL="redis://127.0.0.1:16379/0", S3_ENDPOINT_URL="http://localhost:9000")) == []


def test_the_original_incident_a_hosted_transaction_pooler_is_refused():
    problems = preview_refusals(_ok(DATABASE_URL_TRANSACTION=HOSTED_DB))
    assert any("DATABASE_URL_TRANSACTION" in p for p in problems)


@pytest.mark.parametrize("name", ["DATABASE_URL", "STAGING_DATABASE_URL"])
def test_a_hosted_database_is_refused(name):
    env = _ok()
    env[name] = HOSTED_DB
    assert any(name in p for p in preview_refusals(env))


def test_a_local_database_without_a_throwaway_name_is_refused():
    assert any("name must contain" in p for p in preview_refusals(_ok(DATABASE_URL="postgresql+asyncpg://postgres:pw@127.0.0.1:5432/postgres")))


@pytest.mark.parametrize("env", [{}, {"DATABASE_URL": ""}, {"DATABASE_URL": "   "}])
def test_an_unidentifiable_database_is_refused(env):
    assert any("cannot be identified" in p for p in preview_refusals(env))


@pytest.mark.parametrize("name", ["RATE_LIMIT_REDIS_URL", "CACHE_REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "S3_ENDPOINT_URL"])
def test_a_remote_redis_broker_or_object_store_is_refused(name):
    assert any(name in p for p in preview_refusals(_ok(**{name: "rediss://default:pw@hosted-redis.example:6379/0"})))


@pytest.mark.parametrize("name", ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "PAYSTACK_SECRET_KEY", "RESEND_API_KEY", "TWILIO_AUTH_TOKEN",
                                  "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "SENTRY_DSN", "SLACK_SIGNING_SECRET", "AIRBYTE_API_KEY", "GOOGLE_OAUTH_CLIENT_SECRET"])
def test_an_external_credential_is_refused_when_set_and_accepted_when_empty(name):
    assert any(name in p for p in preview_refusals(_ok(**{name: "set"})))
    assert preview_refusals(_ok(**{name: ""})) == []


def test_internal_signing_secrets_are_not_external_credentials():
    assert preview_refusals(_ok(JWT_SECRET_KEY="x" * 40, SESSION_MIDDLEWARE_SECRET="y" * 40, ENCRYPTION_MASTER_KEY="z", METRICS_AUTH_TOKEN="t")) == []


def test_no_refusal_message_ever_contains_a_value():
    env = _ok(DATABASE_URL=HOSTED_DB, DATABASE_URL_TRANSACTION=HOSTED_DB, STRIPE_SECRET_KEY=SENTINEL, RATE_LIMIT_REDIS_URL=HOSTED_DB)
    with pytest.raises(PreviewRefused) as caught:
        assert_preview_is_isolated(env)
    assert SENTINEL not in str(caught.value) and "hosted-provider" not in str(caught.value)


def test_only_the_explicit_preview_mode_activates_the_guard():
    assert is_preview({"RAG_RUN_MODE": " Preview "}) and not is_preview({}) and not is_preview({"RAG_RUN_MODE": "production"})


# -- the guard is wired into the application settings --------------------------------------------------------------------

def _settings_env(monkeypatch, **values):
    import os

    from api.security import runtime_guard as guard

    base = {"JWT_SECRET_KEY": "j" * 40, "SESSION_MIDDLEWARE_SECRET": "s" * 40, "AUDIT_LOG_HMAC_SECRET_KEY": "a" * 40, "DATABASE_URL": LOCAL_DB}
    base.update(values)
    # The test process may carry the developer's real credentials (conftest loads .env): start from a clean service environment.
    for key in list(os.environ):
        if key.startswith(guard.EXTERNAL_PREFIXES) or key in guard.LOCAL_ENDPOINTS or key in guard.OPTIONAL_DATABASE or key == "RAG_RUN_MODE":
            monkeypatch.delenv(key, raising=False)
    for key, value in base.items():
        monkeypatch.setenv(key, value)


def test_settings_in_preview_mode_refuse_a_hosted_pooler_without_echoing_it(monkeypatch):
    _settings_env(monkeypatch, RAG_RUN_MODE="preview", DATABASE_URL_TRANSACTION=HOSTED_DB)
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)
    assert "DATABASE_URL_TRANSACTION" in str(caught.value) and SENTINEL not in str(caught.value)


def test_settings_in_preview_mode_refuse_an_external_credential(monkeypatch):
    _settings_env(monkeypatch, RAG_RUN_MODE="preview", STRIPE_SECRET_KEY=SENTINEL)
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)
    assert "STRIPE_SECRET_KEY" in str(caught.value) and SENTINEL not in str(caught.value)


def test_settings_in_preview_mode_start_with_a_local_throwaway_setup(monkeypatch):
    _settings_env(monkeypatch, RAG_RUN_MODE="preview")
    assert Settings(_env_file=None).RAG_RUN_MODE == "preview"


def test_without_preview_mode_the_behaviour_is_unchanged(monkeypatch):
    _settings_env(monkeypatch, DATABASE_URL=HOSTED_DB, STRIPE_SECRET_KEY=SENTINEL)
    assert Settings(_env_file=None).DATABASE_URL == HOSTED_DB  # production keeps working exactly as before


# -- the launcher ---------------------------------------------------------------------------------------------------------

POLLUTED_PARENT = {
    "PATH": "C:\\bin", "DATABASE_URL": HOSTED_DB, "DATABASE_URL_TRANSACTION": HOSTED_DB, "RATE_LIMIT_REDIS_URL": "rediss://h.example:6379",
    "STRIPE_SECRET_KEY": SENTINEL, "ANTHROPIC_API_KEY": SENTINEL, "RESEND_API_KEY": SENTINEL, "CELERY_BROKER_URL": "redis://h.example:6379",
    "RAG_ENV_FILE": ".env", "RAG_PREVIEW_DATABASE_URL": LOCAL_DB,
}


def test_the_launcher_never_inherits_service_variables_from_the_shell():
    env = launcher.build_preview_environment(POLLUTED_PARENT, LOCAL_DB)
    assert env["DATABASE_URL"] == LOCAL_DB and env["RAG_RUN_MODE"] == "preview" and env["PATH"] == "C:\\bin"
    assert "DATABASE_URL_TRANSACTION" not in env and "STRIPE_SECRET_KEY" not in env and "ANTHROPIC_API_KEY" not in env and "RESEND_API_KEY" not in env
    assert env["CELERY_BROKER_URL"] == "memory://" and env["RAG_ENV_FILE"] != ".env"
    assert preview_refusals(env) == []


def test_the_launcher_never_loads_the_dotenv_file():
    env = launcher.build_preview_environment(POLLUTED_PARENT, LOCAL_DB)
    assert not (Path(__file__).resolve().parent.parent / env["RAG_ENV_FILE"]).exists()


def test_the_launcher_environment_alone_is_enough_to_build_the_application_settings(monkeypatch):
    """Dogfooding bug: a required setting (SUPPORT_EMAIL) was missing from the sanitized environment, so the preview could not start."""
    import os

    env = launcher.build_preview_environment(POLLUTED_PARENT, LOCAL_DB)
    monkeypatch.setattr(os, "environ", dict(env))
    settings = Settings(_env_file=None)
    assert settings.RAG_RUN_MODE == "preview" and settings.DATABASE_URL == LOCAL_DB and settings.DATABASE_URL_TRANSACTION is None


def test_the_launcher_refuses_without_an_explicit_preview_database(capsys):
    assert launcher.main(["--check"], parent={"PATH": "x"}) == 2
    assert "RAG_PREVIEW_DATABASE_URL" in capsys.readouterr().err


def test_the_launcher_refuses_a_hosted_preview_database_and_does_not_start(monkeypatch, capsys):
    started = []
    monkeypatch.setattr(launcher.subprocess, "call", lambda *a, **k: started.append(a) or 0)
    assert launcher.main([], parent={"PATH": "x", "RAG_PREVIEW_DATABASE_URL": HOSTED_DB}) == 2
    err = capsys.readouterr().err
    assert started == [] and SENTINEL not in err and "hosted-provider" not in err


def test_the_launcher_check_mode_validates_without_starting(monkeypatch, capsys):
    started = []
    monkeypatch.setattr(launcher.subprocess, "call", lambda *a, **k: started.append(a) or 0)
    assert launcher.main(["--check"], parent={"PATH": "x", "RAG_PREVIEW_DATABASE_URL": LOCAL_DB}) == 0
    assert started == []


def test_the_launcher_starts_uvicorn_on_loopback_only_with_the_sanitized_environment(monkeypatch):
    captured = {}
    monkeypatch.setattr(launcher.subprocess, "call", lambda cmd, **kw: captured.update(cmd=cmd, env=kw["env"]) or 0)
    assert launcher.main(["--port", "8123"], parent=POLLUTED_PARENT) == 0
    assert captured["cmd"][-4:] == ["--host", "127.0.0.1", "--port", "8123"]
    assert captured["env"]["DATABASE_URL"] == LOCAL_DB and "STRIPE_SECRET_KEY" not in captured["env"]
