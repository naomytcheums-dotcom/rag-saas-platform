"""Specs 10.3.9 / 13.5.8 error tracking (Sentry) and 10.3.6 / 13.5.5 LLM traces -- tests against LOCAL endpoints.

- Sentry: the REAL sentry-sdk configured by the product (api/security/error_tracking.py) sends to a LOCAL Sentry-compatible ingest (FakeVendor receiving
  envelopes). It is not a Sentry server: no project, grouping or alert rules are exercised. Real check: scripts/validate_sentry_live.py.
- LLM traces: the product's OpenTelemetry setup (api/security/tracing.py) exports the GenAI spans of a product LLM call to a REAL local Jaeger
  (OTLP/HTTP on 127.0.0.1:4318, query API on 16686) when it is running; skipped otherwise. A fake collector is not used for this one.
"""

import gzip
import json
import os
import subprocess
import sys
import textwrap
import time
import uuid

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.security import error_tracking
from vendor_fakes import FakeVendor, Resp, closed_url

JAEGER_OTLP = os.environ.get("JAEGER_OTLP_URL", "http://127.0.0.1:4318")
JAEGER_QUERY = os.environ.get("JAEGER_QUERY_URL", "http://127.0.0.1:16686")


def envelopes(fake: FakeVendor) -> list[list[dict]]:
    """Every envelope received, as a list of (item headers + parsed payload) dicts."""
    parsed = []
    for request in fake.calls("POST"):
        body = request.body
        encoding = request.headers.get("content-encoding")
        if encoding == "gzip":
            body = gzip.decompress(body)
        elif encoding == "br":
            import brotli  # sentry-sdk compresses envelopes with brotli when the package is present

            body = brotli.decompress(body)
        lines = body.split(b"\n")
        items, i = [], 1
        while i + 1 < len(lines):
            header = json.loads(lines[i])
            payload = lines[i + 1]
            try:
                items.append({**header, "payload": json.loads(payload)})
            except ValueError:
                items.append({**header, "payload": None})
            i += 2
        parsed.append(items)
    return parsed


@pytest.fixture
def sentry(monkeypatch):
    import sentry_sdk

    with FakeVendor() as ingest:
        ingest.on("POST", "/api/42/envelope/", Resp(200, {"id": "ok"}))
        monkeypatch.setattr(error_tracking.settings, "SENTRY_DSN", f"http://publickey@{ingest.url.removeprefix('http://')}/42")
        monkeypatch.setattr(error_tracking.settings, "SENTRY_ENVIRONMENT", "contract-test")
        monkeypatch.setattr(error_tracking.settings, "SENTRY_TRACES_SAMPLE_RATE", 0.0)
        error_tracking._initialized = False
        error_tracking.setup_error_tracking()
        assert error_tracking._initialized
        yield ingest
        sentry_sdk.flush(timeout=5)
        sentry_sdk.get_global_scope().set_client(None)
        error_tracking._initialized = False


@pytest.fixture(autouse=True)
def _app_database(db_session):
    """The white-label middleware looks the host up in the database on every request: give the app the in-memory test database, not a server."""
    from api.database import get_db

    async def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def boom_route():
    from fastapi import APIRouter

    router = APIRouter()

    @router.post("/__contract_boom")
    async def boom():
        raise RuntimeError("contract-test explosion")

    app.include_router(router)
    yield "/__contract_boom"
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != "/__contract_boom"]


async def test_an_unhandled_error_reaches_sentry_with_context_but_without_secrets(sentry, boom_route):
    import sentry_sdk

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(boom_route, json={"password": "hunter2-secret", "api_key": "sk-live-secret"}, headers={"Authorization": "Bearer jwt-secret-token", "Cookie": "session=cookie-secret"})
    assert response.status_code == 500
    sentry_sdk.flush(timeout=5)
    sent = [item for envelope in envelopes(sentry) for item in envelope if item.get("type") == "event"]
    assert sent, "no event envelope reached the ingest"
    event = sent[0]["payload"]
    assert event["exception"]["values"][-1]["type"] == "RuntimeError" and "contract-test explosion" in event["exception"]["values"][-1]["value"]
    assert event["environment"] == "contract-test" and event["request"]["url"].endswith("/__contract_boom")
    raw = json.dumps(event)
    for secret in ("hunter2-secret", "sk-live-secret", "jwt-secret-token", "cookie-secret"):
        assert secret not in raw  # send_default_pii=False: bodies, cookies and credentials never leave
    assert "X-Sentry-Auth" and "sentry_key=publickey" in sentry.requests[0].headers["x-sentry-auth"]


async def test_sentry_being_down_does_not_break_or_slow_the_request(monkeypatch, boom_route):
    import sentry_sdk

    monkeypatch.setattr(error_tracking.settings, "SENTRY_DSN", f"http://publickey@{closed_url().removeprefix('http://')}/42")
    error_tracking._initialized = False
    error_tracking.setup_error_tracking()
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        started = time.monotonic()
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            assert (await client.post(boom_route)).status_code == 500
        assert time.monotonic() - started < 3  # events are sent from a background thread
    finally:
        sentry_sdk.get_global_scope().set_client(None)
        error_tracking._initialized = False


def test_a_celery_worker_starts_error_tracking_too(monkeypatch):
    """The worker never ran setup_error_tracking(): its task failures reached no tracker. Firing the real worker signals must now start it."""
    import sentry_sdk
    from api.tasks import celery_app as module

    monkeypatch.setattr(error_tracking.settings, "SENTRY_DSN", "http://publickey@127.0.0.1:1/42")
    error_tracking._initialized = False
    try:
        module.worker_process_init.send(sender=None)
        assert error_tracking._initialized and sentry_sdk.get_client().is_active()
    finally:
        sentry_sdk.get_global_scope().set_client(None)
        error_tracking._initialized = False


async def test_a_failing_celery_task_is_captured_by_sentry(sentry):
    import sentry_sdk
    from celery import Celery

    module_app = Celery("contract")
    module_app.conf.task_always_eager = True
    module_app.conf.task_eager_propagates = False

    @module_app.task(name="contract.fail")
    def fail():
        raise ValueError("task blew up")

    from sentry_sdk.integrations.celery import CeleryIntegration  # the product enables it in setup_error_tracking()

    assert any(isinstance(i, CeleryIntegration) for i in sentry_sdk.get_client().integrations.values())
    result = fail.apply()
    assert result.failed()
    sentry_sdk.flush(timeout=5)
    events = [item["payload"] for envelope in envelopes(sentry) for item in envelope if item.get("type") == "event"]
    assert any("task blew up" in json.dumps(e) for e in events)


# ------------------------------------------------------------------------------------------------------------------------------------ traces


def jaeger_up() -> bool:
    try:
        return httpx.get(f"{JAEGER_QUERY}/api/services", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


TRACE_SCRIPT = textwrap.dedent(
    """
    import asyncio, sys
    from fastapi import FastAPI
    from opentelemetry import trace
    from api.security.tracing import setup_tracing
    from api.services.llm_providers import chat_completion
    from api.config import settings

    settings.ANTHROPIC_API_KEY = "trace-test-key"
    setup_tracing(FastAPI())
    async def main():
        answer = await chat_completion([{"role": "user", "content": "ping"}], provider="anthropic", api_base=sys.argv[1], max_retries=0)
        print("ANSWER", answer)
    asyncio.run(main())
    trace.get_tracer_provider().force_flush(10000)
    trace.get_tracer_provider().shutdown()
    """
)


def run_traced_llm_call(vendor_url: str, service: str, otlp: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "OTEL_ENABLED": "true", "OTEL_SERVICE_NAME": service, "OTEL_EXPORTER_OTLP_ENDPOINT": otlp, "OTEL_TRACES_SAMPLER_ARG": "1.0"}
    return subprocess.run([sys.executable, "-c", TRACE_SCRIPT, vendor_url], env=env, capture_output=True, text=True, timeout=180)


@pytest.mark.skipif(not jaeger_up(), reason="the local Jaeger (OTLP 4318 / query 16686) is not running")
def test_llm_call_spans_with_genai_attributes_arrive_in_a_real_trace_backend():
    service = f"rag-contract-{uuid.uuid4().hex[:8]}"
    with FakeVendor() as llm:
        llm.on("POST", "/v1/messages", Resp(200, {"id": "m", "type": "message", "role": "assistant", "model": "claude-x", "stop_reason": "end_turn",
                                                    "content": [{"type": "text", "text": "pong"}], "usage": {"input_tokens": 12, "output_tokens": 4}}))
        done = run_traced_llm_call(llm.url, service, JAEGER_OTLP)
    assert done.returncode == 0 and "ANSWER pong" in done.stdout, done.stderr[-2000:]
    spans = []
    for _ in range(20):  # Jaeger indexes asynchronously
        found = httpx.get(f"{JAEGER_QUERY}/api/traces", params={"service": service, "limit": 20}, timeout=5).json().get("data", [])
        spans = [s for t in found for s in t["spans"]]
        if any(s["operationName"].startswith("chat ") for s in spans):
            break
        time.sleep(1)
    chat = next(s for s in spans if s["operationName"].startswith("chat "))
    tags = {t["key"]: t["value"] for t in chat["tags"]}
    assert tags["gen_ai.operation.name"] == "chat" and tags["gen_ai.system"] == "anthropic"
    assert tags["gen_ai.usage.input_tokens"] == 12 and tags["gen_ai.usage.output_tokens"] == 4
    assert "trace-test-key" not in json.dumps(chat)  # the key never travels in a span


def test_traces_backend_down_does_not_break_the_llm_call():
    with FakeVendor() as llm:
        llm.on("POST", "/v1/messages", Resp(200, {"id": "m", "type": "message", "role": "assistant", "model": "c", "stop_reason": "end_turn",
                                                    "content": [{"type": "text", "text": "pong"}], "usage": {"input_tokens": 1, "output_tokens": 1}}))
        done = run_traced_llm_call(llm.url, "rag-contract-down", closed_url())
    assert done.returncode == 0 and "ANSWER pong" in done.stdout, done.stderr[-2000:]
