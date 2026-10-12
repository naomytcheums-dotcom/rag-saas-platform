"""scripts/run_live_tests.py: it must pass a provider's variables and nothing else, and refuse anything that could mean a live (paid) account.
Pure function tests: no database, network or provider call."""

import pytest

from scripts.run_isolated_tests import IsolationRefused
from scripts.run_live_tests import PROVIDERS, build_live_environment, read_env_file

LOCAL = {"PATH": "x", "RAG_TEST_DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:25432/rag_test_integration"}


def test_a_test_key_is_passed_with_its_companion_and_nothing_else_from_the_file():
    values = {"STRIPE_SECRET_KEY": "sk_test_not_a_real_key", "STRIPE_TEST_PRICE_ID": "price_x", "PAYSTACK_SECRET_KEY": "sk_test_other", "DATABASE_URL": "postgresql://real"}
    env = build_live_environment(LOCAL, "stripe", values)
    assert env["STRIPE_SECRET_KEY"] == "sk_test_not_a_real_key" and env["STRIPE_TEST_PRICE_ID"] == "price_x"
    assert "PAYSTACK_SECRET_KEY" not in env
    assert env["DATABASE_URL"] == LOCAL["RAG_TEST_DATABASE_URL"]  # the file cannot redirect the database


@pytest.mark.parametrize("provider", ["stripe", "paystack"])
@pytest.mark.parametrize("key", ["sk_live_abc", "rk_live_abc", "whatever", "pk_test_abc"])
def test_a_key_that_is_not_a_test_key_is_refused(provider, key):
    names = PROVIDERS[provider]["names"]
    with pytest.raises(IsolationRefused) as caught:
        build_live_environment(LOCAL, provider, {names[0]: key, names[1]: "x"})
    assert key not in str(caught.value)  # the refusal never echoes the value


def test_an_incomplete_file_is_refused_and_names_the_missing_variable_only():
    with pytest.raises(IsolationRefused, match="STRIPE_TEST_PRICE_ID"):
        build_live_environment(LOCAL, "stripe", {"STRIPE_SECRET_KEY": "sk_test_x"})


def test_oauth_providers_need_every_variable():
    full = {name: "value" for name in PROVIDERS["google-drive"]["names"]}
    assert set(PROVIDERS["google-drive"]["names"]) <= set(build_live_environment(LOCAL, "google-drive", full))
    full.pop("GOOGLE_DRIVE_CLIENT_SECRET")
    with pytest.raises(IsolationRefused):
        build_live_environment(LOCAL, "google-drive", full)


def test_the_database_guard_still_applies_in_live_mode():
    with pytest.raises(IsolationRefused):
        build_live_environment({"PATH": "x", "RAG_TEST_DATABASE_URL": "postgresql+asyncpg://u:p@aws-0.pooler.supabase.com:6543/postgres"}, "notion", {"NOTION_API_TOKEN": "t"})


def test_env_file_parsing_ignores_comments_and_quotes(tmp_path):
    path = tmp_path / "x.env"
    path.write_text("# comment\n\nA=1\nB='two'\nC=\"three\"\nnot a pair\n", encoding="utf-8")
    assert read_env_file(path) == {"A": "1", "B": "two", "C": "three"}
