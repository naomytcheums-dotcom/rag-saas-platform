"""Network-free regression checks for the staging-only allowlist."""

import subprocess
import sys
from base64 import urlsafe_b64decode
from os import environ
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from scripts import staging_validate
from scripts.staging_target import (
    STAGING_HOST,
    STAGING_POOLER_HOST,
    STAGING_POOLER_USER,
    StagingTargetError,
    isolated_environment,
    validate_staging_url,
)


def test_exact_staging_target_and_async_driver():
    url = validate_staging_url(f"postgresql://postgres:unit-test-only@{STAGING_HOST}:5432/postgres")
    assert url.drivername == "postgresql+asyncpg"
    assert url.host == STAGING_HOST
    assert dict(url.query) == {"ssl": "require"}


def test_confirmed_staging_session_pooler_target():
    url = validate_staging_url(
        f"postgresql://{STAGING_POOLER_USER}:unit-test-only@{STAGING_POOLER_HOST}:5432/postgres"
    )
    assert url.host == STAGING_POOLER_HOST
    assert url.username == STAGING_POOLER_USER
    assert dict(url.query) == {"ssl": "require"}


@pytest.mark.parametrize("user,host,port", [
    ("postgres.otherproject", STAGING_POOLER_HOST, 5432),
    ("postgres", STAGING_POOLER_HOST, 5432),
    (STAGING_POOLER_USER, STAGING_HOST, 5432),
    (STAGING_POOLER_USER, STAGING_POOLER_HOST, 6543),
    (STAGING_POOLER_USER, "untrusted.pooler.invalid", 5432),
])
def test_session_pooler_refuses_other_projects_and_transaction_mode(user, host, port):
    with pytest.raises(StagingTargetError):
        validate_staging_url(f"postgresql://{user}:unit-test-only@{host}:{port}/postgres")


@pytest.mark.parametrize("value", [
    "postgresql://postgres:unit-test-only@production.supabase.co:5432/postgres",
    f"postgresql://postgres:unit-test-only@{STAGING_HOST}.attacker.test:5432/postgres",
    f"postgresql://postgres:unit-test-only@{STAGING_HOST}:6543/postgres",
    f"postgresql://postgres:unit-test-only@{STAGING_HOST}:5432/other",
    f"postgresql://other:unit-test-only@{STAGING_HOST}:5432/postgres",
    f"postgresql://postgres:unit-test-only@{STAGING_HOST}:5432/postgres?host=production",
    f"postgresql://postgres:[YOUR-STAGING-PASSWORD]@{STAGING_HOST}:5432/postgres",
    "not-a-url",
])
def test_refuses_all_nonallowlisted_or_placeholder_targets(value):
    with pytest.raises(StagingTargetError) as captured:
        validate_staging_url(value)
    assert "unit-test-only" not in str(captured.value)
    assert value not in str(captured.value)


def test_isolated_environment_uses_fresh_encryption_keys_without_provider_credentials(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "must-not-be-inherited")
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "must-not-be-inherited")
    monkeypatch.setenv("ENCRYPTION_MASTER_KEY", "must-not-be-inherited")
    url = make_url("postgresql+asyncpg://localtest:localtest@127.0.0.1:1/isolated_tests")
    first = isolated_environment(url)
    second = isolated_environment(url)
    assert "RESEND_API_KEY" not in first
    assert first["PYTHON_DOTENV_DISABLED"] == "1"
    for key in ("SECRET_ENCRYPTION_KEY", "ENCRYPTION_MASTER_KEY"):
        assert len(urlsafe_b64decode(first[key])) == 32
        assert first[key] != second[key]
        assert first[key] != "must-not-be-inherited"


def test_isolated_environment_prevents_third_party_dotenv_loading(monkeypatch, tmp_path):
    url = make_url("postgresql+asyncpg://localtest:localtest@127.0.0.1:1/isolated_tests")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", isolated_environment(url)["PYTHON_DOTENV_DISABLED"])
    monkeypatch.delenv("STAGING_TEST_DOTENV_MARKER", raising=False)
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("STAGING_TEST_DOTENV_MARKER=must-not-load\n", encoding="utf-8")
    assert load_dotenv(dotenv_file) is False
    assert "STAGING_TEST_DOTENV_MARKER" not in environ


@pytest.mark.parametrize("entrypoint", [
    ["-m", "scripts.staging_validate"],
    ["scripts\\staging_validate.py"],
])
def test_staging_runner_supports_module_and_script_entrypoints(entrypoint):
    result = subprocess.run(
        [sys.executable, *entrypoint, "inspect"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "DRY RUN: no connection" in result.stdout


def test_runner_redacts_credentials_without_redacting_boolean_token_flags(monkeypatch, capsys):
    result = subprocess.CompletedProcess([], 0, stdout="head 0132 credential-sensitive", stderr="")
    monkeypatch.setattr(staging_validate.subprocess, "run", lambda *args, **kwargs: result)
    assert staging_validate.run_process(
        [], {"HF_HUB_DISABLE_IMPLICIT_TOKEN": "1", "JWT_SECRET_KEY": "credential-sensitive"}, "password-sensitive",
    ) == 0
    assert capsys.readouterr().out == "head 0132 [REDACTED]"


def test_idor_runner_passes_browser_identities_and_writes_evidence(monkeypatch, tmp_path):
    target = validate_staging_url(
        f"postgresql://{STAGING_POOLER_USER}:unit-test-only@{STAGING_POOLER_HOST}:5432/postgres"
    )
    monkeypatch.setattr(staging_validate, "staging_url", lambda: target)
    monkeypatch.setattr(staging_validate, "ROOT", tmp_path)
    identities = {
        "RAG_STAGING_USER_A": "00000000-0000-4000-8000-000000000001",
        "RAG_STAGING_ORG_A": "00000000-0000-4000-8000-000000001001",
        "RAG_STAGING_USER_B": "00000000-0000-4000-8000-000000000002",
        "RAG_STAGING_ORG_B": "00000000-0000-4000-8000-000000001002",
    }
    for key, value in identities.items():
        monkeypatch.setenv(key, value)
    observed = {}

    def run(arguments, environment, password):
        observed.update(arguments=arguments, environment=environment)
        return 0

    monkeypatch.setattr(staging_validate, "run_process", run)
    assert staging_validate.tests(idor_only=True) == 0
    assert "tests/test_staging_full_idor.py" in observed["arguments"]
    assert "tests/test_staging_idor.py" not in observed["arguments"]
    assert any(arg.endswith("idor-browser-tenants.xml") for arg in observed["arguments"])
    assert observed["environment"]["RAG_STAGING_TESTS"] == "YES"
    for key, value in identities.items():
        assert observed["environment"][key] == value
