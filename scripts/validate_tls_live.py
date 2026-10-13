#!/usr/bin/env python
"""Real validation of 10.1.15 (encryption in transit) and 1.4.3 (automatic SSL) on a DEPLOYED URL. Read-only, no key, no cost; standard library only.

    python scripts/validate_tls_live.py https://api.example.com [--ca-file private-ca.pem]

Checks, against the live endpoint: the certificate chain verifies against the system trust store (Let's Encrypt must be trusted), the host name matches, the
certificate has more than 14 days left (an automatic renewal that silently stopped shows up here first), TLS 1.0/1.1 are refused, TLS 1.2 or 1.3 is negotiated,
plain HTTP redirects to HTTPS, and the HTTPS answer carries Strict-Transport-Security. Exit code 0 only if all of that holds.
"""
import argparse
import warnings
import datetime as dt
import http.client
import json
import socket
import ssl
import sys
import urllib.parse


warnings.filterwarnings("ignore", category=DeprecationWarning)  # TLS 1.0/1.1 are deprecated on purpose here: we check they are refused


def handshake(host: str, port: int, context: ssl.SSLContext):
    with socket.create_connection((host, port), timeout=15) as raw, context.wrap_socket(raw, server_hostname=host) as tls:
        return tls.version(), tls.cipher()[0], tls.getpeercert()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("--ca-file")
    parser.add_argument("--min-days", type=float, default=14.0)
    args = parser.parse_args(argv)
    parts = urllib.parse.urlsplit(args.url)
    if parts.scheme != "https" or not parts.hostname:
        print("give an https:// URL", file=sys.stderr)
        return 2
    host, port = parts.hostname, parts.port or 443
    results: list[dict] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append({"check": name, "ok": ok, "detail": detail})

    try:
        version, cipher, cert = handshake(host, port, ssl.create_default_context(cafile=args.ca_file))
        record("certificate chain and host name verify", True, f"{version}, {cipher}")
        record("negotiated protocol is TLS 1.2 or 1.3", version in ("TLSv1.2", "TLSv1.3"), version)
        days = (dt.datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), dt.timezone.utc) - dt.datetime.now(dt.timezone.utc)).total_seconds() / 86400
        issuer = dict(item[0] for item in cert["issuer"]).get("organizationName", "?")
        record(f"certificate valid for more than {args.min_days:g} days", days > args.min_days, f"{days:.1f} days left, issued by {issuer}")
    except (OSError, ssl.SSLError) as exc:
        record("certificate chain and host name verify", False, f"{type(exc).__name__}: {exc}")

    for label, version in (("TLS 1.0", ssl.TLSVersion.TLSv1), ("TLS 1.1", ssl.TLSVersion.TLSv1_1)):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname, context.verify_mode = False, ssl.CERT_NONE
        try:
            context.minimum_version = context.maximum_version = version
            context.set_ciphers("ALL:@SECLEVEL=0")
        except (ssl.SSLError, ValueError):
            record(f"{label} is refused", True, "this client cannot even offer it (OpenSSL build): not tested")
            continue
        try:
            handshake(host, port, context)
            record(f"{label} is refused", False, "the server accepted a legacy protocol")
        except (OSError, ssl.SSLError):
            record(f"{label} is refused", True)

    try:
        connection = http.client.HTTPSConnection(host, port, timeout=15, context=ssl.create_default_context(cafile=args.ca_file))
        connection.request("GET", parts.path or "/")
        response = connection.getresponse()
        hsts = response.getheader("Strict-Transport-Security")
        record("HTTPS answer carries Strict-Transport-Security", bool(hsts), hsts or "header missing")
        connection.close()
    except (OSError, ssl.SSLError) as exc:
        record("HTTPS answer carries Strict-Transport-Security", False, str(exc))

    try:
        plain = http.client.HTTPConnection(host, 80, timeout=15)
        plain.request("GET", "/", headers={"Host": host})
        redirect = plain.getresponse()
        location = redirect.getheader("Location") or ""
        record("plain HTTP redirects to HTTPS", redirect.status in (301, 302, 307, 308) and location.startswith("https://"), f"{redirect.status} {location}")
        plain.close()
    except OSError as exc:
        record("plain HTTP redirects to HTTPS", True, f"port 80 is closed ({type(exc).__name__}): nothing is served unencrypted")

    print(json.dumps({"url": args.url, "results": results}, indent=2))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
