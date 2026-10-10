"""Spec 13.2.11 - the post-deploy smoke script, run against a real local HTTP server (no mocks of urllib)."""

import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

spec = importlib.util.spec_from_file_location("post_deploy_smoke", Path(__file__).resolve().parents[1] / "scripts" / "post_deploy_smoke.py")
smoke = importlib.util.module_from_spec(spec)
sys.modules["post_deploy_smoke"] = smoke
spec.loader.exec_module(smoke)


def _server(routes):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = routes.get(self.path, (404, b""))
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _healthy_routes(database="ok"):
    return {
        "/health": (200, b'{"status":"ok"}'),
        "/health/ready": (200, json.dumps({"database": database}).encode()),
        "/openapi.json": (200, json.dumps({"paths": {f"/p{i}": {} for i in range(150)}}).encode()),
        "/billing/plans": (200, b"[]"),
        "/organizations": (401, b"{}"),
        "/": (200, b"<html></html>"), "/login": (200, b"<HTML>"), "/register": (200, b"<html>"),
    }


def test_a_healthy_deployment_passes_every_check(capsys):
    server = _server(_healthy_routes())
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        assert smoke.main(["--api", base, "--frontend", base]) == 0
    finally:
        server.shutdown()
    assert "FAIL" not in capsys.readouterr().out


def test_an_unreachable_database_fails_the_smoke_test(capsys):
    server = _server(_healthy_routes(database="unreachable"))
    try:
        assert smoke.main(["--api", f"http://127.0.0.1:{server.server_port}"]) == 1
    finally:
        server.shutdown()
    assert "[FAIL] api reports its database as reachable" in capsys.readouterr().out


def test_an_open_protected_route_is_reported():
    routes = _healthy_routes()
    routes["/organizations"] = (200, b"[]")
    server = _server(routes)
    try:
        results = smoke.check_api(f"http://127.0.0.1:{server.server_port}")
    finally:
        server.shutdown()
    assert [r.name for r in results if not r.ok] == ["a protected route refuses anonymous calls"]
