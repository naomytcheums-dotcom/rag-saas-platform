"""Phase 5 of the 2026-10-12 security audit (SEC-009): a secret that reaches a log line must not reach the console, `system_logs`, the hosted Loki or Sentry.

Before: only the quoted `key: "value"` form was masked, and only on two paths (the JSON formatter, system_logs). The Loki handler shipped `self.format(record)` as is, a
`Bearer` header, `password=...`, a `postgresql://user:password@host` URL, a raw provider key or an exception message went through, and the Celery worker never masked anything.
All fake values below. Offline.
"""

import io
import logging

import pytest

import api.security.logging_correlation as lc

SECRETS = {
    "bearer": ("calling the API with Authorization: Bearer abc123def456ghi789", "abc123def456ghi789"),
    "unquoted password": ("login failed password=hunter22secret for user 12", "hunter22secret"),
    "unquoted token": ("refresh token: tok_0123456789abcdef rejected", "tok_0123456789abcdef"),
    "url credentials": ("could not connect to postgresql://app:S3cr3tPw@db.example.com:5432/x", "S3cr3tPw"),
    "anthropic key": ("provider answered 401 for key sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWX", "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWX"),
    "aws key": ("uploading with AKIAABCDEFGHIJKLMNOP", "AKIAABCDEFGHIJKLMNOP"),
    "jwt": ("session eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123xyz expired", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123xyz"),
    "quoted (already covered)": ('payload {"password": "quoted-secret-value"}', "quoted-secret-value"),
}


@pytest.mark.parametrize("name", SECRETS)
def test_mask_sensitive_removes_every_secret_shape_and_keeps_the_context(name):
    message, secret = SECRETS[name]
    masked = lc.mask_sensitive(message)
    assert secret not in masked
    assert "***" in masked
    assert masked.split()[0] == message.split()[0]  # the line is still readable


@pytest.mark.parametrize("message", [
    "max_tokens=100 and 5 tokens used",
    "processing document 8f1c2d3e for organization 12",
    "the user logged in from 10.0.0.1",
    "context window limit reached: 4096",
])
def test_ordinary_lines_are_left_alone(message):
    assert lc.mask_sensitive(message) == message


@pytest.fixture
def masking_factory(monkeypatch):
    """Install the record factory for this test only, then restore the previous one."""
    previous = logging.getLogRecordFactory()
    monkeypatch.setattr(lc, "_record_factory_installed", False)
    lc.install_log_masking()
    yield
    logging.setLogRecordFactory(previous)


def _logger_with_buffer():
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger = logging.getLogger("phase5.masking")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, buffer


def test_a_secret_never_reaches_any_handler_not_even_through_lazy_arguments_or_an_exception(masking_factory):
    logger, buffer = _logger_with_buffer()
    logger.error("login failed password=%s token: %s", "hunter22secret", "tok_0123456789abcdef")
    try:
        raise RuntimeError("could not connect to postgresql://app:S3cr3tPw@db.example.com/x")
    except RuntimeError:
        logger.exception("startup failed")
    output = buffer.getvalue()
    for secret in ("hunter22secret", "tok_0123456789abcdef", "S3cr3tPw"):
        assert secret not in output
    assert "db.example.com" in output  # context kept


def test_a_line_without_a_secret_keeps_its_template_and_arguments(masking_factory):
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            seen.append((record.msg, record.args))

    logger = logging.getLogger("phase5.untouched")
    logger.handlers, logger.propagate = [Capture()], False
    logger.setLevel(logging.INFO)
    logger.info("hello %s", "world")
    assert seen == [("hello %s", ("world",))]  # lazy formatting and Sentry's message grouping are unchanged


def test_a_broken_logging_call_still_behaves_as_before(masking_factory, monkeypatch):
    logger, _buffer = _logger_with_buffer()
    monkeypatch.setattr(logging, "raiseExceptions", False)  # a malformed call is reported by the handler, never raised by the masking
    logger.info("only one placeholder %s %s", "a")


def test_the_celery_worker_installs_the_masking_on_its_own(monkeypatch):
    from api.tasks import celery_app

    previous = logging.getLogRecordFactory()
    monkeypatch.setattr(lc, "_record_factory_installed", False)
    try:
        celery_app._mask_secrets_in_worker_logs()
        assert logging.getLogRecordFactory() is not previous
        record = logging.getLogRecordFactory()("w", logging.ERROR, __file__, 1, "token=abcdef123456", (), None)
        assert "abcdef123456" not in record.getMessage()
    finally:
        logging.setLogRecordFactory(previous)
