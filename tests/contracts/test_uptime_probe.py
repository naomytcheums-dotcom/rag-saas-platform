"""Spec 11.3.4 uptime monitoring: scripts/uptime_probe.py against local servers that are up, degraded, slow, down or serving a short-lived self-signed
certificate. The probe is real code; the servers are local stand-ins. Pointing it at the real deployment is the one external step
(`python scripts/uptime_probe.py https://<your-api> --interval 60 --webhook <slack-url>` from any cron / scheduled CI job)."""

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import uptime_probe  # noqa: E402

from vendor_fakes import FakeVendor, Resp, closed_url  # noqa: E402


def probe(*argv) -> tuple[int, list[dict]]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = uptime_probe.main(list(argv))
    return code, [json.loads(line) for line in buffer.getvalue().splitlines() if line.startswith("{")]


def test_a_healthy_instance_is_ok():
    with FakeVendor() as api:
        api.on("GET", "/health", Resp(200, {"status": "ok"}))
        api.on("GET", "/health/ready", Resp(200, {"status": "ready"}))
        code, (result,) = probe(api.url)
    assert code == 0 and result["ok"] and result["status"] == 200 and result["ready_status"] == 200 and result["problems"] == []


def test_not_ready_is_reported_with_the_reason_the_instance_gives():
    with FakeVendor() as api:
        api.on("GET", "/health", Resp(200, {"status": "ok"}))
        api.on("GET", "/health/ready", Resp(503, {"status": "degraded", "checks": {"database": "down"}}))
        code, (result,) = probe(api.url)
    assert code == 1 and not result["ok"] and "503" in result["problems"][0] and "database" in result["problems"][0]


@pytest.mark.parametrize("status", [500, 502, 503, 404])
def test_error_statuses_are_down(status):
    with FakeVendor() as api:
        api.on("GET", "/health", Resp(status, {"detail": "x"}))
        code, (result,) = probe(api.url)
    assert code == 1 and result["status"] == status and "health" in result["problems"][0]


def test_unreachable_and_hanging_instances_are_down():
    code, (result,) = probe(closed_url(), "--timeout", "5")
    assert code == 1 and result["status"] is None and "unreachable" in result["problems"][0]
    with FakeVendor() as api:
        api.on("GET", "/health", Resp(200, {}, delay=2.0))
        code, (result,) = probe(api.url, "--timeout", "0.4")
    assert code == 1 and "unreachable" in result["problems"][0] and "timed out" in result["problems"][0].lower()


def test_a_slow_answer_is_a_problem_even_if_it_is_a_200():
    with FakeVendor() as api:
        api.on("GET", "/health", Resp(200, {}, delay=0.6))
        api.on("GET", "/health/ready", Resp(200, {}))
        code, (result,) = probe(api.url, "--max-latency", "0.2")
    assert code == 1 and "slow" in result["problems"][0]


def test_tls_certificate_is_verified_and_its_expiry_is_watched():
    with tempfile.TemporaryDirectory() as directory, FakeVendor(tls_directory=directory) as api:
        api.on("GET", "/health", Resp(200, {}))
        api.on("GET", "/health/ready", Resp(200, {}))
        code, (trusted,) = probe(api.url, "--ca-file", api.ca_file)
        assert code == 0 and 28 < trusted["cert_days_left"] <= 30
        code, (untrusted,) = probe(api.url)  # an unknown CA: the certificate is NOT silently accepted
        assert code == 1 and "unreachable" in untrusted["problems"][0] and "CERTIFICATE_VERIFY_FAILED" in untrusted["problems"][0]
        code, (expiring,) = probe(api.url, "--ca-file", api.ca_file, "--min-cert-days", "60")
        assert code == 1 and "certificate expires" in expiring["problems"][0]


def test_the_webhook_is_called_once_per_state_change_not_once_per_check():
    with FakeVendor() as api, FakeVendor() as chat:
        chat.on("POST", "/hook", Resp(200, "ok"))
        api.on("GET", "/health", [Resp(200, {}), Resp(500, {}), Resp(500, {}), Resp(500, {}), Resp(200, {}), Resp(200, {})])
        api.on("GET", "/health/ready", Resp(200, {}))
        code, results = probe(api.url, "--interval", "0.05", "--count", "6", "--webhook", f"{chat.url}/hook")
    assert [r["ok"] for r in results] == [True, False, False, False, True, True]
    messages = [r.json()["text"] for r in chat.calls("POST", "/hook")]
    assert len(messages) == 2 and "DOWN" in messages[0] and "back up" in messages[1]  # one alert for the outage, one for the recovery
    assert code == 0


def test_an_unreachable_webhook_does_not_stop_the_probe(capsys):
    with FakeVendor() as api:
        api.on("GET", "/health", [Resp(200, {}), Resp(500, {}), Resp(500, {})])
        api.on("GET", "/health/ready", Resp(200, {}))
        code, results = probe(api.url, "--interval", "0.05", "--count", "3", "--webhook", f"{closed_url()}/hook", "--timeout", "3")
    assert len(results) == 3 and code == 1
    assert "alert_not_delivered" in capsys.readouterr().err
