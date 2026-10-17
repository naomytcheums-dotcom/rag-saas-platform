"""Audit item 10.1.9 (SSRF protection): inventory of the places that call httpx directly instead of through `ssrf_safe_client()`.

A direct httpx call is only safe when the host it talks to is a constant (a vendor API) or a platform setting, never a value a tenant user
can type. Reviewed 2026-10-11 module by module: hosts come from constants or settings. EXCEPTION since the per-organization credentials (D17): the importers whose service
can be self-hosted (Jira, Confluence, WooCommerce, Salesforce, GitLab...) or sits on a customer sub-domain (Zendesk, Shopify, Teamwork...) now read the address from the
organization's stored credentials. api/services/connector_credentials.py validates it (https, no credentials or custom port, vendor domain when vendor-hosted, public address
checked at save time AND again at use time) but the HTTP call itself is a plain httpx call: a host that changes its DNS answer between the check and the call (DNS rebinding)
is not blocked. Moving those calls to ssrf_safe_client() closes that window; it was not done because the existing tests of these modules patch httpx.AsyncClient. `api/tools/human_escalation.py` posts to a caller-supplied webhook URL and
therefore goes through the SSRF-safe client (tests below).

This test fails when a NEW file calls httpx directly: either route the call through `ssrf_safe_client()` (api/services/url_fetching.py), or review
the host and add the file to REVIEWED_DIRECT_CALLS with the reason it is safe. It also fails when an entry no longer has a direct call, so the
list cannot rot."""

import ast
import pathlib

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
_CALLS = {"AsyncClient", "Client", "get", "post", "put", "patch", "delete", "request", "stream"}

# Guard modules and the one documented exception.
GUARD_AND_EXCEPTIONS = {
    "api/services/url_fetching.py": "the SSRF guard itself (public-address check at connection time)",
    "api/services/outbound_http.py": "the SSRF guard for webhooks (public-address check at connection time)",
    "api/security/enterprise_oidc.py": "an enterprise identity provider may legitimately live on an internal network; documented gap in tests/test_ssrf_hardening.py",
}

# Reviewed 2026-10-11: constant vendor host or platform setting, no host supplied by a tenant user.
REVIEWED_DIRECT_CALLS = {
    "api/routers/integrations_universal.py",
    "api/security/geoip.py",
    "api/security/loki_handler.py",
    "api/security/password_strength.py",
    "api/services/activecampaign_extraction.py",
    "api/services/airbyte_client.py",
    "api/services/airtable_extraction.py",
    "api/services/asana_extraction.py",
    "api/services/azure_devops_extraction.py",
    "api/services/basecamp_extraction.py",
    "api/services/billing_paystack.py",
    "api/services/bitbucket_extraction.py",
    "api/services/box_extraction.py",
    "api/services/chat_integrations/discord.py",
    "api/services/chat_integrations/slack.py",
    "api/services/chat_integrations/teams.py",
    "api/services/clickup_extraction.py",
    "api/services/coda_extraction.py",
    "api/services/confluence_extraction.py",
    "api/services/display_currency.py",
    "api/services/docusign_extraction.py",
    "api/services/dropbox_extraction.py",
    "api/services/email.py",
    "api/services/fine_tuning_providers.py",
    "api/services/github_extraction.py",
    "api/services/gitlab_extraction.py",
    "api/services/google_drive_extraction.py",
    "api/services/hive_extraction.py",
    "api/services/hubspot_extraction.py",
    "api/services/intercom_extraction.py",
    "api/services/jira_extraction.py",
    "api/services/klaviyo_extraction.py",
    "api/services/linear_extraction.py",
    "api/services/mailchimp_extraction.py",
    "api/services/miro_extraction.py",
    "api/services/monday_extraction.py",
    "api/services/nifty_extraction.py",
    "api/services/notion_extraction.py",
    "api/services/onedrive_extraction.py",
    "api/services/opa_policy.py",
    "api/services/pipedrive_extraction.py",
    "api/services/pipefy_extraction.py",
    "api/services/podio_extraction.py",
    "api/services/process_street_extraction.py",
    "api/services/resend_domains.py",
    "api/services/salesforce_extraction.py",
    "api/services/security_alerts.py",
    "api/services/shopify_extraction.py",
    "api/services/smartsheet_extraction.py",
    "api/services/smartsuite_extraction.py",
    "api/services/teamwork_extraction.py",
    "api/services/trello_extraction.py",
    "api/services/voice.py",
    "api/services/woocommerce_extraction.py",
    "api/services/wrike_extraction.py",
    "api/services/zendesk_extraction.py",
    "api/services/zoho_extraction.py",
    "api/tools/calendar_tools.py",
    "api/tools/email_tools.py",
    "api/tools/github_tools.py",
    "api/tools/web_search.py",
}


def _files_with_direct_httpx_calls() -> set[str]:
    found = set()
    for path in (ROOT / "api").rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("api/alembic/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "httpx" and node.func.attr in _CALLS):
                found.add(relative)
                break
    return found


def test_every_direct_httpx_call_has_been_reviewed():
    unreviewed = sorted(_files_with_direct_httpx_calls() - set(REVIEWED_DIRECT_CALLS) - set(GUARD_AND_EXCEPTIONS))
    assert not unreviewed, (
        f"{unreviewed} call httpx directly. Use ssrf_safe_client() from api/services/url_fetching.py, or review the target host "
        "and add the file to REVIEWED_DIRECT_CALLS in tests/test_outbound_http_inventory.py."
    )


def test_the_reviewed_list_has_no_stale_entry():
    stale = sorted((set(REVIEWED_DIRECT_CALLS) | set(GUARD_AND_EXCEPTIONS)) - _files_with_direct_httpx_calls())
    assert not stale, f"{stale} no longer call httpx directly: remove them from the reviewed list."


async def test_the_escalation_webhook_cannot_reach_a_private_address(db_session):
    """notify_via_webhook posts to whatever URL it is given. A real HTTP server listens on loopback: before the fix it received the POST,
    now the connection is refused before any request is sent. (A closed port would fail either way, which proves nothing.)"""
    import threading
    import uuid
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from api.tools.human_escalation import notify_via_webhook

    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        escalation = type("E", (), {"id": uuid.uuid4(), "issue": "x", "priority": "low", "status": "open"})()
        with pytest.raises((ValueError, httpx.HTTPError)):
            await notify_via_webhook(f"http://127.0.0.1:{server.server_port}/hook", escalation)
    finally:
        server.shutdown()
        server.server_close()
    assert received == [], "the webhook reached a server on a loopback address"
