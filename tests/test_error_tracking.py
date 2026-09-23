"""Phase 5, Étape 7 -- Sentry error tracking, real no-op unless
SENTRY_DSN is set (api/security/error_tracking.py)."""

import api.security.error_tracking as error_tracking


def _reset():
    error_tracking._initialized = False


def test_setup_error_tracking_is_a_real_noop_without_a_dsn(monkeypatch):
    _reset()
    monkeypatch.setattr(error_tracking.settings, "SENTRY_DSN", None)

    error_tracking.setup_error_tracking()

    assert error_tracking._initialized is False


def test_error_tracking_status_reports_disabled_without_a_dsn(monkeypatch):
    _reset()
    monkeypatch.setattr(error_tracking.settings, "SENTRY_DSN", None)

    status = error_tracking.error_tracking_status()

    assert status == {"enabled": False, "initialized": False, "environment": None}


def test_setup_error_tracking_initializes_real_sentry_sdk_when_dsn_is_set(monkeypatch):
    _reset()
    monkeypatch.setattr(error_tracking.settings, "SENTRY_DSN", "https://public@sentry.example.com/1")
    monkeypatch.setattr(error_tracking.settings, "SENTRY_ENVIRONMENT", "test")

    error_tracking.setup_error_tracking()

    assert error_tracking._initialized is True

    import sentry_sdk

    client = sentry_sdk.get_client()
    assert client.is_active()
    assert client.options["environment"] == "test"
    assert client.options["send_default_pii"] is False

    sentry_sdk.get_global_scope().set_client(None)


def test_error_tracking_status_reports_environment_once_configured(monkeypatch):
    _reset()
    monkeypatch.setattr(error_tracking.settings, "SENTRY_DSN", "https://public@sentry.example.com/1")
    monkeypatch.setattr(error_tracking.settings, "SENTRY_ENVIRONMENT", "staging")

    error_tracking.setup_error_tracking()
    status = error_tracking.error_tracking_status()

    assert status == {"enabled": True, "initialized": True, "environment": "staging"}

    import sentry_sdk

    sentry_sdk.get_global_scope().set_client(None)


def test_setup_error_tracking_does_not_reinitialize_once_already_initialized(monkeypatch):
    """Validation criterion: idempotence -- un second appel (ex. reload
    module) ne doit pas re-init Sentry inutilement."""
    _reset()
    monkeypatch.setattr(error_tracking.settings, "SENTRY_DSN", "https://public@sentry.example.com/1")

    error_tracking.setup_error_tracking()
    assert error_tracking._initialized is True

    monkeypatch.setattr(error_tracking.settings, "SENTRY_DSN", None)
    error_tracking.setup_error_tracking()

    assert error_tracking._initialized is True

    import sentry_sdk

    sentry_sdk.get_global_scope().set_client(None)
