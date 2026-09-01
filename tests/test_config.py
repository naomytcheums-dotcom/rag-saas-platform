"""Unit tests for api/config.py's cross-field validation -- the settings
themselves are pure logic, tested in isolation same as api/security/*.py."""

import pytest
from pydantic import ValidationError

from api.config import Settings, settings


def _settings(**overrides):
    """Builds a real Settings instance using this environment's actual
    required values (DATABASE_URL, JWT_SECRET_KEY, SESSION_MIDDLEWARE_SECRET)
    -- those aren't what's under test here, just fields Settings() can't
    be constructed without -- with the fields under test overridden."""
    defaults = {
        "DATABASE_URL": settings.DATABASE_URL,
        "JWT_SECRET_KEY": settings.JWT_SECRET_KEY,
        "SESSION_MIDDLEWARE_SECRET": settings.SESSION_MIDDLEWARE_SECRET,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_deletion_reminder_days_must_be_less_than_purge_delay_days():
    """4.6: a misconfiguration where the reminder window is >= the purge
    delay would make the "last chance" reminder eligible the instant
    deletion is requested -- a duplicate of the immediate confirmation
    email, defeating the point of a second, later warning. Must be
    caught at startup (a pydantic ValidationError), not discovered in
    production as "why did this user get two emails the same day."""
    with pytest.raises(ValidationError):
        _settings(ACCOUNT_PURGE_DELAY_DAYS=30, ACCOUNT_DELETION_REMINDER_DAYS_BEFORE=30)

    with pytest.raises(ValidationError):
        _settings(ACCOUNT_PURGE_DELAY_DAYS=30, ACCOUNT_DELETION_REMINDER_DAYS_BEFORE=31)


def test_deletion_reminder_days_less_than_purge_delay_days_is_accepted():
    valid = _settings(ACCOUNT_PURGE_DELAY_DAYS=30, ACCOUNT_DELETION_REMINDER_DAYS_BEFORE=3)
    assert valid.ACCOUNT_DELETION_REMINDER_DAYS_BEFORE == 3


def test_restore_token_expiry_must_be_less_than_the_purge_delay_in_minutes():
    """5.7 audit finding: confirm_account_restore trusts its token's own
    expiry rather than re-checking deletion_scheduled_at, so a restore
    token must never outlive the account it points to. 2 days = 2880
    minutes; a 30-day (43200-minute) purge delay must reject a token
    expiry at or beyond that many minutes."""
    with pytest.raises(ValidationError):
        _settings(ACCOUNT_PURGE_DELAY_DAYS=2, ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES=2 * 24 * 60)

    with pytest.raises(ValidationError):
        _settings(ACCOUNT_PURGE_DELAY_DAYS=2, ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES=2 * 24 * 60 + 1)


def test_restore_token_expiry_less_than_the_purge_delay_in_minutes_is_accepted():
    valid = _settings(ACCOUNT_PURGE_DELAY_DAYS=30, ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES=1440)
    assert valid.ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES == 1440


def test_support_email_is_required():
    """RGPD Art. 12: every email api/services/email.py sends must carry a
    real contact address (see its _send() footer). Asserted directly on
    the field's own pydantic metadata (rather than by constructing a
    Settings() and hoping SUPPORT_EMAIL is absent) because this project's
    .env always defines it via pydantic-settings' env_file loading --
    Settings(**overrides) can never actually be missing it in this
    environment, so the only real proof "no default" holds is that the
    field itself declares none."""
    assert Settings.model_fields["SUPPORT_EMAIL"].is_required()


def test_database_url_rejects_the_plain_postgresql_driver():
    """Not new this session -- just previously untested directly (only
    ever exercised implicitly by every other test using the real,
    already-valid DATABASE_URL). A misconfigured deployment pointing at
    postgresql:// instead of postgresql+asyncpg:// must fail at startup,
    not with a confusing driver-mismatch error the first time a route
    touches the database."""
    with pytest.raises(ValidationError):
        _settings(DATABASE_URL="postgresql://user:password@localhost:5432/db")
