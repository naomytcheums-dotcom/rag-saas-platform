"""PROD-003: the database pool must not default to more connections than a session-mode pooler allows."""

import pytest

from api.db_pool import resolve_pool_settings


def test_transaction_pooler_keeps_the_larger_defaults():
    assert resolve_pool_settings({}, transaction_mode=True) == (5, 10, 60)


def test_direct_or_session_mode_uses_the_small_defaults():
    assert resolve_pool_settings({}, transaction_mode=False) == (3, 2, 60)


def test_the_per_process_budget_is_at_most_three_plus_two_without_a_transaction_pooler():
    size, overflow, _timeout = resolve_pool_settings({}, transaction_mode=False)
    assert (size, overflow) == (3, 2)
    assert size + overflow < 15  # a single process can never exhaust a 15-connection session-mode cap on its own; 60 per host could


@pytest.mark.parametrize("transaction_mode", [True, False])
def test_environment_variables_override_both_defaults(transaction_mode):
    env = {"SQLALCHEMY_POOL_SIZE": "2", "SQLALCHEMY_MAX_OVERFLOW": "1", "SQLALCHEMY_POOL_TIMEOUT": "15"}
    assert resolve_pool_settings(env, transaction_mode) == (2, 1, 15)


def test_a_partial_override_keeps_the_other_defaults():
    assert resolve_pool_settings({"SQLALCHEMY_POOL_SIZE": "1"}, transaction_mode=False) == (1, 2, 60)
