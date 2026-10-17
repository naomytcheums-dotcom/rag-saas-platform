#!/usr/bin/env python
"""Uptime probe for a deployed instance: checks liveness (/health), readiness (/health/ready), latency and TLS certificate expiry, and alerts a webhook on
state changes. Standard library only, so it runs anywhere (cron, a CI schedule, a sidecar container) and needs no account with an uptime SaaS.

    python scripts/uptime_probe.py https://api.example.com                       # one check, exit code 1 when unhealthy
    python scripts/uptime_probe.py https://api.example.com --interval 60          # keep checking every 60 s
    python scripts/uptime_probe.py https://api.example.com --interval 60 --webhook https://hooks.slack.com/services/...   # alert when it goes down / comes back

Each check prints one JSON line. The webhook receives a Slack-compatible `{"text": ...}` body ONLY when the state changes (down after up, up after down),
so a long outage is one alert, not one per minute. `--ca-file` trusts a private CA (self-signed test certificates); the certificate is otherwise always verified.
"""

import argparse
import datetime as dt
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def fetch(url: str, timeout: float, context: ssl.SSLContext | None) -> tuple[int | None, float, str | None, bytes]:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": "rag-uptime-probe/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read(65536)
            return response.status, (time.monotonic() - started) * 1000, None, body
    except urllib.error.HTTPError as exc:  # the server answered, with an error status
        return exc.code, (time.monotonic() - started) * 1000, None, exc.read(65536)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError, ConnectionError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return None, (time.monotonic() - started) * 1000, f"{type(reason).__name__}: {reason}", b""


def certificate_days_left(url: str, timeout: float, context: ssl.SSLContext) -> float | None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        return None
    try:
        with socket.create_connection((parts.hostname, parts.port or 443), timeout=timeout) as raw, context.wrap_socket(raw, server_hostname=parts.hostname) as tls:
            not_after = tls.getpeercert()["notAfter"]
    except (OSError, ssl.SSLError, KeyError):
        return None
    expires = dt.datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), dt.timezone.utc)
    return (expires - dt.datetime.now(dt.timezone.utc)).total_seconds() / 86400


def check(base_url: str, args, context: ssl.SSLContext) -> dict:
    base = base_url.rstrip("/")
    result: dict = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "url": base, "ok": True, "problems": []}
    status, latency, error, _ = fetch(base + args.live_path, args.timeout, context)
    result.update(status=status, latency_ms=round(latency))
    if status is None:
        result["problems"].append(f"unreachable ({error})")
    elif status != 200:
        result["problems"].append(f"{args.live_path} answered {status}")
    elif latency > args.max_latency * 1000:
        result["problems"].append(f"slow: {latency / 1000:.1f}s > {args.max_latency}s")
    if status == 200 and args.ready_path:
        ready_status, _, ready_error, body = fetch(base + args.ready_path, args.timeout, context)
        result["ready_status"] = ready_status
        if ready_status != 200:
            detail = ""
            try:
                detail = json.dumps(json.loads(body)) [:200] if body else ""
            except ValueError:
                detail = body[:200].decode("utf-8", "replace")
            result["problems"].append(f"{args.ready_path} answered {ready_status if ready_status else ready_error} {detail}".strip())
    days = certificate_days_left(base, args.timeout, context)
    if days is not None:
        result["cert_days_left"] = round(days, 1)
        if days < args.min_cert_days:
            result["problems"].append(f"TLS certificate expires in {days:.1f} days (< {args.min_cert_days})")
    result["ok"] = not result["problems"]
    return result


def notify(webhook: str, text: str, timeout: float) -> None:
    request = urllib.request.Request(webhook, data=json.dumps({"text": text}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(request, timeout=timeout).read()
    except (urllib.error.URLError, OSError) as exc:
        print(json.dumps({"alert_not_delivered": str(exc)}), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("--live-path", default="/health")
    parser.add_argument("--ready-path", default="/health/ready", help="empty string to skip the readiness check")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-latency", type=float, default=3.0, help="seconds above which the liveness answer counts as a problem")
    parser.add_argument("--min-cert-days", type=float, default=14.0)
    parser.add_argument("--interval", type=float, default=0.0, help="seconds between checks; 0 = a single check")
    parser.add_argument("--count", type=int, default=0, help="stop after N checks (0 = forever when --interval is set)")
    parser.add_argument("--webhook", default=None, help="Slack-compatible incoming webhook notified on up<->down changes")
    parser.add_argument("--ca-file", default=None, help="PEM file of a private CA / self-signed certificate to trust")
    args = parser.parse_args(argv)

    context = ssl.create_default_context(cafile=args.ca_file)
    previous_ok: bool | None = None
    done, last = 0, 0
    while True:
        result = check(args.url, args, context)
        print(json.dumps(result), flush=True)
        if args.webhook and previous_ok is not None and result["ok"] != previous_ok:
            text = f":white_check_mark: {result['url']} is back up" if result["ok"] else f":rotating_light: {result['url']} is DOWN: " + "; ".join(result["problems"])
            notify(args.webhook, text, args.timeout)
        previous_ok = result["ok"]
        last = 0 if result["ok"] else 1
        done += 1
        if not args.interval or (args.count and done >= args.count):
            return last
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
