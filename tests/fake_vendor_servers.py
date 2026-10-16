"""LOCAL FAKES of external services, used by the contract tests of the custom domain (1.4.1), the e-mail domain (1.4.5) and the sender address (1.4.9).

THESE ARE FAKES. They speak the real wire protocols (DNS over UDP through dnspython's message codec; Resend's documented REST routes and error shapes) so that
OUR client code is exercised end to end over a real socket, but they are written from the vendors' public documentation: a green run proves that our code
behaves correctly against a server that follows that documentation, NOT that Resend or a customer's DNS provider behave that way today. The real validation is a
separate step that needs a real domain and a real Resend account (see docs/project-handover/e2e_evidence/billing_RESUME.md).
"""

import json
import re
import socketserver
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import dns.message
import dns.rcode
import dns.rdatatype
import dns.rrset


# --------------------------------------------------------------------------------------------------------------------- DNS (UDP)


class FakeDnsServer:
    """An authoritative-looking UDP DNS server holding TXT zones: `publish("_rag-saas-verify.app.example.test", "token")`. Unknown names answer NXDOMAIN."""

    def __init__(self) -> None:
        self.zone: dict[str, list[str]] = {}
        self.queries: list[str] = []
        outer = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                data, sock = self.request
                try:
                    query = dns.message.from_wire(data)
                except Exception:  # noqa: BLE001 -- garbage on the wire is ignored, like a real server does
                    return
                response = dns.message.make_response(query)
                question = query.question[0]
                name = str(question.name).rstrip(".").lower()
                outer.queries.append(f"{dns.rdatatype.to_text(question.rdtype)} {name}")
                values = outer.zone.get(name)
                if values is None:
                    response.set_rcode(dns.rcode.NXDOMAIN)
                elif question.rdtype == dns.rdatatype.TXT:
                    response.answer.append(dns.rrset.from_text_list(question.name, 60, "IN", "TXT", [f'"{v}"' for v in values]))
                sock.sendto(response.to_wire(), self.client_address)

        self._server = socketserver.ThreadingUDPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def nameserver(self) -> str:
        return f"127.0.0.1:{self.port}"

    def publish(self, name: str, value: str) -> None:
        self.zone.setdefault(name.rstrip(".").lower(), []).append(value)

    def unpublish(self, name: str) -> None:
        self.zone.pop(name.rstrip(".").lower(), None)

    def start(self) -> "FakeDnsServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


# --------------------------------------------------------------------------------------------------------------------- Resend (HTTP)

_DOMAIN_PATH = re.compile(r"^/domains/([^/]+)(/verify)?$")


class FakeResend:
    """Resend's REST API as documented: Bearer authentication; `POST /domains` creates a domain with its DNS `records`; `GET /domains/{id}` reports a status that
    moves to "verified" only after `POST /domains/{id}/verify` was called AND every record is really published in the (fake) DNS; `POST /emails` refuses a `from`
    whose domain is not verified in the account with a 403 `validation_error`. Sent e-mails are kept in `.sent`."""

    def __init__(self, api_key: str, dns_server: FakeDnsServer) -> None:
        self.api_key = api_key
        self.dns = dns_server
        self.domains: dict[str, dict] = {}
        self.verify_requested: set[str] = set()
        self.sent: list[dict] = []
        self.requests: list[tuple[str, str]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                return

            def _reply(self, status: int, body: dict) -> None:
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(length) or b"{}")

            def _authorized(self) -> bool:
                if self.headers.get("Authorization") != f"Bearer {outer.api_key}":
                    self._reply(401, {"statusCode": 401, "name": "validation_error", "message": "API key is invalid"})
                    return False
                return True

            def do_POST(self):
                outer.requests.append(("POST", self.path))
                if not self._authorized():
                    return
                if self.path == "/domains":
                    name = self._body().get("name", "")
                    if any(d["name"] == name for d in outer.domains.values()):
                        return self._reply(403, {"statusCode": 403, "name": "validation_error", "message": "This domain has already been registered"})
                    domain = outer._new_domain(name)
                    outer.domains[domain["id"]] = domain
                    return self._reply(201, outer._view(domain))
                if self.path == "/emails":
                    body = self._body()
                    sender = body.get("from", "")
                    address = re.search(r"<([^>]+)>", sender).group(1) if "<" in sender else sender
                    domain_name = address.rsplit("@", 1)[-1].lower()
                    known = next((d for d in outer.domains.values() if d["name"] == domain_name), None)
                    if known is None or outer._status(known) != "verified":
                        return self._reply(403, {"statusCode": 403, "name": "validation_error", "message": f"The {domain_name} domain is not verified. Please, add and verify your domain."})
                    outer.sent.append(body)
                    return self._reply(200, {"id": str(uuid.uuid4())})
                match = _DOMAIN_PATH.match(self.path)
                if match and match.group(2):
                    domain = outer.domains.get(match.group(1))
                    if domain is None:
                        return self._reply(404, {"statusCode": 404, "name": "not_found", "message": "Domain not found"})
                    outer.verify_requested.add(domain["id"])
                    return self._reply(200, {"object": "domain", "id": domain["id"]})
                self._reply(404, {"statusCode": 404, "name": "not_found", "message": "Route not found"})

            def do_GET(self):
                outer.requests.append(("GET", self.path))
                if not self._authorized():
                    return
                match = _DOMAIN_PATH.match(self.path)
                domain = outer.domains.get(match.group(1)) if match and not match.group(2) else None
                if domain is None:
                    return self._reply(404, {"statusCode": 404, "name": "not_found", "message": "Domain not found"})
                self._reply(200, outer._view(domain))

            def do_DELETE(self):
                outer.requests.append(("DELETE", self.path))
                if not self._authorized():
                    return
                match = _DOMAIN_PATH.match(self.path)
                if match and outer.domains.pop(match.group(1), None) is not None:
                    return self._reply(200, {"object": "domain", "id": match.group(1), "deleted": True})
                self._reply(404, {"statusCode": 404, "name": "not_found", "message": "Domain not found"})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    # -- the account's domains --------------------------------------------------------------------------------------------------------
    def _new_domain(self, name: str) -> dict:
        domain_id = str(uuid.uuid4())
        records = [
            {"record": "SPF", "name": "send", "type": "MX", "ttl": "Auto", "status": "not_started", "value": "feedback-smtp.local.example", "priority": 10, "_dns_name": f"send.{name}", "_dns_value": "feedback-smtp.local.example"},
            {"record": "SPF", "name": "send", "type": "TXT", "ttl": "Auto", "status": "not_started", "value": "v=spf1 include:local.example ~all", "_dns_name": f"send.{name}", "_dns_value": "v=spf1 include:local.example ~all"},
            {"record": "DKIM", "name": "resend._domainkey", "type": "TXT", "ttl": "Auto", "status": "not_started", "value": "p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQ", "_dns_name": f"resend._domainkey.{name}", "_dns_value": "p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQ"},
        ]
        return {"id": domain_id, "name": name, "status": "not_started", "created_at": "2026-10-13T10:00:00.000Z", "region": "us-east-1", "records": records}

    def _published(self, record: dict) -> bool:
        if record["type"] != "TXT":
            return True  # the MX row is not checked in this fake (dnspython server answers TXT only)
        return record["_dns_value"] in self.dns.zone.get(record["_dns_name"], [])

    def _status(self, domain: dict) -> str:
        if domain["id"] not in self.verify_requested:
            return "not_started"
        return "verified" if all(self._published(r) for r in domain["records"]) else "pending"

    def _view(self, domain: dict) -> dict:
        status = self._status(domain)
        records = [{k: v for k, v in r.items() if not k.startswith("_dns")} | {"status": "verified" if status == "verified" else ("pending" if status == "pending" else "not_started")} for r in domain["records"]]
        return {"object": "domain", "id": domain["id"], "name": domain["name"], "status": status, "created_at": domain["created_at"], "region": domain["region"], "records": records}

    def publish_records(self, domain_name: str) -> None:
        """What the customer does at their DNS provider after reading Resend's instructions."""
        for domain in self.domains.values():
            if domain["name"] == domain_name:
                for r in domain["records"]:
                    if r["type"] == "TXT":
                        self.dns.publish(r["_dns_name"], r["_dns_value"])

    def register_verified_domain(self, domain_name: str) -> None:
        """A domain the platform itself already verified in its Resend account (the default sender's domain)."""
        domain = self._new_domain(domain_name)
        self.domains[domain["id"]] = domain
        self.verify_requested.add(domain["id"])
        self.publish_records(domain_name)

    def start(self) -> "FakeResend":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
