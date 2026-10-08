import pytest

from scripts import check_env_ready


def test_presence_never_prints_values_and_discovers_prefixed_names(capsys):
    values = {name: "sensitive-value-not-to-print" for name in check_env_ready.VARIABLES}
    values["STAGING_DATABASE_URL"] = "postgresql://example:synthetic@localhost:1/test"
    values["S3_ADDITIONAL_SETTING"] = "sensitive-value-not-to-print"
    assert check_env_ready.report(values)
    output = capsys.readouterr().out
    assert "sensitive-value-not-to-print" not in output
    assert "postgresql://" not in output
    assert "S3_ADDITIONAL_SETTING=PRESENT" in output
    assert "DATABASE_PASSWORD_PLACEHOLDER=False" in output
    assert "guarded staging runner preflight" in output


@pytest.mark.parametrize("password", ["[PLACEHOLDER]", "%5BPLACEHOLDER%5D"])
def test_bracketed_database_password_refuses_readiness(password, capsys):
    values = {name: "synthetic" for name in check_env_ready.VARIABLES}
    values["STAGING_DATABASE_URL"] = f"postgresql://example:{password}@localhost:1/test"
    assert not check_env_ready.report(values)
    output = capsys.readouterr().out
    assert "DATABASE_PASSWORD_PLACEHOLDER=True" in output
    assert password not in output


def test_missing_settings_produce_names_and_next_action(capsys):
    assert not check_env_ready.report({})
    output = capsys.readouterr().out
    assert "STAGING_DATABASE_URL=MISSING" in output
    assert "RESEND_API_KEY=MISSING" in output
    assert "NEXT_ACTION=Provision" in output


def test_loader_does_not_read_general_dotenv(monkeypatch):
    paths = []
    monkeypatch.setattr(check_env_ready, "dotenv_values", lambda path: paths.append(path) or {
        "S3_BUCKET_NAME": "synthetic-staging-value",
    })
    monkeypatch.setenv("S3_BUCKET_NAME", "synthetic-process-value")
    assert check_env_ready.load_values()["S3_BUCKET_NAME"] == "synthetic-process-value"
    assert paths == [check_env_ready.ROOT / ".env.staging"]
