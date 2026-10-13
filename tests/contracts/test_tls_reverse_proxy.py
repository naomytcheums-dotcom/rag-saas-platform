"""Specs 10.1.15 encryption in transit and 1.4.3 automatic SSL, locally: the repository's OWN nginx reverse-proxy template
(nginx/templates/default.conf.template, the one docker-compose.selfhosted.yml deploys) is run in a real nginx container with a SELF-SIGNED certificate in
front of the real API (uvicorn). The only edit to the template is the upstream address of `api`/`frontend` (container -> host).

What this proves: the TLS configuration of the template (TLS 1.2/1.3 only, certificate verified by clients, HTTP -> HTTPS redirect, HSTS, forwarded protocol
reaching the API, Secure/HSTS behaviour of the API behind the proxy). What it does NOT prove: that Let's Encrypt can issue a certificate for a public domain
(tests/test_acme_integration.py exercises the real ACME protocol against Let's Encrypt STAGING; a full issuance needs a public DNS name) nor that the
deployed Render/Vercel endpoints terminate TLS correctly (scripts/validate_tls_live.py checks a deployed URL).
"""

import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time

import httpx
import pytest

from vendor_fakes import FakeVendor, Resp, make_self_signed_certificate

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMAGE = "nginx:1.29-alpine"


def docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, timeout=20).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


pytestmark = pytest.mark.skipif(not docker_ready(), reason=f"docker with the {IMAGE} image is needed")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def windows_path(path: str) -> str:
    return path.replace("\\", "/")


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    work = tmp_path_factory.mktemp("tls")
    cert_dir = work / "live" / "localhost"
    cert_dir.mkdir(parents=True)
    cert, key = make_self_signed_certificate(str(cert_dir))
    shutil.copy(cert, cert_dir / "fullchain.pem")
    shutil.copy(key, cert_dir / "privkey.pem")

    api_port, https_port, http_port = free_port(), free_port(), free_port()
    api_env = {**os.environ, "COOKIE_SECURE": "true", "FRONTEND_URL": f"https://localhost:{https_port}", "RATE_LIMIT_ENABLED": "false"}
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(api_port), "--log-level", "warning"],
                           cwd=REPO, env=api_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with FakeVendor() as frontend:
        frontend.on("GET", "/*", Resp(200, "<html>frontend</html>", headers={"Content-Type": "text/html"}))
        templates = work / "templates"
        templates.mkdir()
        for name in os.listdir(os.path.join(REPO, "nginx", "templates")):
            text = open(os.path.join(REPO, "nginx", "templates", name), encoding="utf-8").read()
            text = text.replace("http://api:8000/", f"http://host.docker.internal:{api_port}/").replace("http://frontend:3000/", f"http://host.docker.internal:{frontend._server.server_address[1]}/")
            open(templates / name, "w", encoding="utf-8", newline="\n").write(text)
        name = f"rag-tls-test-{https_port}"
        run = subprocess.run(
            ["docker", "run", "-d", "--rm", "--name", name, "-e", "DOMAIN_NAME=localhost", "--add-host", "host.docker.internal:host-gateway",
             "-v", f"{windows_path(str(templates))}:/etc/nginx/templates:ro", "-v", f"{windows_path(str(work / 'live'))}:/etc/letsencrypt/live:ro",
             "-p", f"127.0.0.1:{https_port}:443", "-p", f"127.0.0.1:{http_port}:80", IMAGE],
            capture_output=True, text=True, timeout=120, env={**os.environ, "MSYS_NO_PATHCONV": "1"},
        )
        assert run.returncode == 0, run.stderr
        try:
            deadline = time.time() + 120
            while time.time() < deadline:
                try:
                    if httpx.get(f"http://127.0.0.1:{api_port}/health", timeout=2).status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(1)
            else:
                pytest.fail("the API did not start: " + (api.stdout.read(2000).decode(errors="replace") if api.poll() is not None else "timeout"))
            for _ in range(30):
                try:
                    socket.create_connection(("127.0.0.1", https_port), timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.5)
            yield {"https": https_port, "http": http_port, "api": api_port, "ca": cert}
        finally:
            subprocess.run(["docker", "stop", name], capture_output=True, timeout=60)
            api.terminate()
            try:
                api.wait(timeout=15)
            except subprocess.TimeoutExpired:
                api.kill()


def tls_context(ca: str | None, minimum=None, maximum=None) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()
    if minimum:
        context.minimum_version = minimum
    if maximum:
        context.maximum_version = maximum
    return context


def handshake(port: int, context: ssl.SSLContext, server_hostname: str = "localhost") -> tuple[str, str]:
    with socket.create_connection(("127.0.0.1", port), timeout=10) as raw, context.wrap_socket(raw, server_hostname=server_hostname) as tls:
        return tls.version(), tls.cipher()[0]


def test_the_certificate_is_verified_by_a_client_that_trusts_it_and_refused_by_one_that_does_not(stack):
    version, _cipher = handshake(stack["https"], tls_context(stack["ca"]))
    assert version in ("TLSv1.3", "TLSv1.2")
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(stack["https"], tls_context(None))  # self-signed: an unknown CA must be refused, not silently accepted
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(stack["https"], tls_context(stack["ca"]), server_hostname="other.example.test")  # right CA, wrong host name


def test_only_tls_1_2_and_1_3_are_accepted(stack):
    unverified = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    unverified.check_hostname, unverified.verify_mode = False, ssl.CERT_NONE
    for legacy in (ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname, context.verify_mode = False, ssl.CERT_NONE
        try:
            context.minimum_version = context.maximum_version = legacy
            context.set_ciphers("ALL:@SECLEVEL=0")
        except (ssl.SSLError, ValueError):
            pytest.skip("this OpenSSL build cannot even offer TLS 1.0/1.1, which already rules them out on the client side")
        with pytest.raises(ssl.SSLError):
            handshake(stack["https"], context)
    tls12 = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls12.check_hostname, tls12.verify_mode = False, ssl.CERT_NONE
    tls12.minimum_version = tls12.maximum_version = ssl.TLSVersion.TLSv1_2
    assert handshake(stack["https"], tls12)[0] == "TLSv1.2"
    tls13 = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls13.check_hostname, tls13.verify_mode = False, ssl.CERT_NONE
    tls13.minimum_version = tls13.maximum_version = ssl.TLSVersion.TLSv1_3
    assert handshake(stack["https"], tls13)[0] == "TLSv1.3"


def test_plain_http_is_redirected_to_https(stack):
    response = httpx.get(f"http://127.0.0.1:{stack['http']}/some/path?x=1", headers={"Host": "localhost"}, follow_redirects=False, timeout=10)
    assert response.status_code == 301 and response.headers["location"] == "https://localhost/some/path?x=1"


def test_security_headers_and_the_api_behind_the_proxy(stack):
    with httpx.Client(verify=tls_context(stack["ca"]), timeout=15) as client:
        base = f"https://localhost:{stack['https']}"
        health = client.get(f"{base}/api/health")
        assert health.status_code == 200
        assert health.headers["strict-transport-security"].startswith("max-age=")  # set by nginx and by the API (COOKIE_SECURE=true)
        assert health.headers["x-content-type-options"] == "nosniff"
        home = client.get(f"{base}/")
        assert home.status_code == 200 and "frontend" in home.text and "strict-transport-security" in home.headers


def test_the_api_sees_https_and_issues_secure_cookies_behind_the_proxy(stack):
    with httpx.Client(verify=tls_context(stack["ca"]), timeout=30) as client:
        base = f"https://localhost:{stack['https']}/api"
        email = f"tls-{int(time.time())}@example.com"
        response = client.post(f"{base}/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})
        cookies = [value for name, value in response.headers.multi_items() if name.lower() == "set-cookie"]
        if not cookies:
            pytest.skip(f"register answered {response.status_code} without cookies: this build keeps tokens out of cookies")
        assert all(re.search(r";\s*secure", cookie, re.I) for cookie in cookies), cookies  # a cookie over TLS must be Secure
        assert all(re.search(r"httponly", cookie, re.I) for cookie in cookies if "session" in cookie.lower() or "refresh" in cookie.lower())
