"""A programmable LOCAL fake server used by the vendor contract tests (tests/contracts/).

It is a FAKE: it speaks the wire protocol of a vendor (paths, headers, JSON shapes, status codes) so the product's real HTTP client code runs
unchanged over a real loopback socket. Nothing here proves a real vendor account works; the real validation is scripts/validate_<vendor>_live.py.

    with FakeVendor() as fake:
        fake.on("POST", "/v1/messages", Resp(200, {...}))
        fake.on("POST", "/v1/messages", [Resp(429, {...}, headers={"retry-after": "0"}), Resp(200, {...})])   # a sequence, the last one repeats
        fake.on("POST", "/search", lambda req: Resp(200, {"echo": req.json()}))
        ... call fake.url ...
        fake.requests  # every request received, in order
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlsplit


@dataclass
class Req:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]  # lower-cased names
    body: bytes

    def json(self):
        return json.loads(self.body.decode("utf-8")) if self.body else None

    def form(self) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(self.body.decode("utf-8")).items()}


@dataclass
class Resp:
    status: int = 200
    body: object = field(default_factory=dict)  # dict/list -> JSON, str -> text, bytes -> raw
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0  # seconds to wait before answering (timeout tests)
    drop: bool = False  # close the connection without answering


def make_self_signed_certificate(directory: str, hostnames=("localhost", "127.0.0.1")) -> tuple[str, str]:
    """A throw-away self-signed server certificate for tests (`cert.pem`, `key.pem`); the certificate doubles as its own CA file for clients."""
    import datetime
    import ipaddress
    import os

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostnames[0])])
    sans = []
    for host in hostnames:
        try:
            sans.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            sans.append(x509.DNSName(host))
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False).add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = os.path.join(directory, "cert.pem"), os.path.join(directory, "key.pem")
    with open(cert_path, "wb") as handle:
        handle.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as handle:
        handle.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    return cert_path, key_path


class FakeVendor:
    def __init__(self, host: str = "127.0.0.1", tls_directory: str | None = None):
        """`tls_directory`: serve HTTPS with a fresh self-signed certificate written there; `ca_file` is what a verifying client must trust."""
        self._routes: list[tuple[str, str, object]] = []
        self._cursor: dict[int, int] = {}
        self.requests: list[Req] = []
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # silence
                pass

            def _serve(self):
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length) if length else b""
                parts = urlsplit(self.path)
                req = Req(self.command, parts.path, parse_qs(parts.query), {k.lower(): v for k, v in self.headers.items()}, raw)
                resp = outer._dispatch(req)
                if resp.delay:
                    time.sleep(resp.delay)
                if resp.drop:
                    self.close_connection = True
                    return
                if isinstance(resp.body, (dict, list)):
                    payload, ctype = json.dumps(resp.body).encode(), "application/json"
                elif isinstance(resp.body, str):
                    payload, ctype = resp.body.encode(), "text/plain; charset=utf-8"
                else:
                    payload, ctype = bytes(resp.body), "application/octet-stream"
                self.send_response(resp.status)
                headers = {"Content-Type": ctype, **resp.headers}
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _serve

        self._server = ThreadingHTTPServer((host, 0), Handler)
        self._server.daemon_threads = True
        self.ca_file = None
        self._scheme = "http"
        if tls_directory:
            import ssl

            self.ca_file, key_file = make_self_signed_certificate(tls_directory)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(self.ca_file, key_file)
            self._server.socket = context.wrap_socket(self._server.socket, server_side=True)
            self._scheme = "https"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    # -- configuration -------------------------------------------------------------------------------------------------------------------
    def on(self, method: str, path: str, response):
        """`path` matches exactly, or as a prefix when it ends with '*'. `response` is a Resp, a callable(Req)->Resp or a list of those."""
        self._routes.append((method.upper(), path, response))
        return self

    def _dispatch(self, req: Req) -> Resp:
        with self._lock:
            self.requests.append(req)
            for index, (method, path, response) in enumerate(self._routes):
                if method != req.method and method != "*":
                    continue
                if path.endswith("*") and not req.path.startswith(path[:-1]):
                    continue
                if not path.endswith("*") and path != req.path:
                    continue
                if isinstance(response, list):
                    position = self._cursor.get(index, 0)
                    self._cursor[index] = position + 1
                    response = response[min(position, len(response) - 1)]
                if callable(response):
                    response = response(req)
                return response
        return Resp(404, {"error": f"fake vendor has no route for {req.method} {req.path}"})

    # -- life cycle ----------------------------------------------------------------------------------------------------------------------
    @property
    def url(self) -> str:
        return f"{self._scheme}://{self._server.server_address[0]}:{self._server.server_address[1]}"

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    def calls(self, method: str | None = None, path: str | None = None) -> list[Req]:
        return [r for r in self.requests if (method is None or r.method == method) and (path is None or r.path == path)]


def closed_url() -> str:
    """http URL of a loopback port nothing listens on (the vendor is 'down': connection refused)."""
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"
