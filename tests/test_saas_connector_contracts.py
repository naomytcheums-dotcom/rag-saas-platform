"""Provider-independent contract of the SaaS extraction modules (api/services/<name>_extraction.py).

tests/test_crm_import_ingestion.py replaces the fetch functions entirely and tests/test_connector_credentials.py checks which Jira credentials a
route sends; neither runs the fetch functions themselves. Here every function runs for real, outside any organization scope (so
`connector_settings` falls back to `api.config.settings`), against an `httpx.MockTransport` installed on the module's own `httpx` name only:

  * a disabled flag or a missing credential raises the module error before any request is sent;
  * 429 raises the dedicated rate-limit error (a subclass of the module error), any other failure raises the module error with the status,
    except the multi-object connectors (HubSpot, Pipedrive, Salesforce) which log the failed object type and carry on;
  * a successful answer becomes records whose `id` and `text` carry the provider fields, optional fields left out when absent.

Success payloads follow the shape each module reads. The modules whose request or response shape does not match the provider's public API
(Salesforce, Zendesk, Asana, Jira, Hive, Nifty, Pipefy, Process Street, Teamwork) get no success test here: pinning that shape would present it
as correct. They are still checked for the flag, the credentials and the error statuses.
"""

import base64
import importlib
import json
import logging
import types
from dataclasses import dataclass, field

import httpx
import pytest

from api.config import settings
from api.services import connector_credentials


@dataclass
class Recorded:
    method: str
    url: str
    host: str
    path: str
    headers: httpx.Headers
    params: dict[str, str]
    body: object


@dataclass
class FakeHttp:
    """Scripted answers, one per request in order; every request is recorded."""

    responses: list[httpx.Response]
    requests: list[Recorded] = field(default_factory=list)
    client_kwargs: list[dict] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        content = request.read()
        body = None
        if content:
            if request.headers.get("content-type", "").startswith("application/json"):
                body = json.loads(content)
            else:
                body = content.decode()
        self.requests.append(
            Recorded(
                method=request.method,
                url=str(request.url),
                host=request.url.host,
                path=request.url.path,
                headers=request.headers,
                params=dict(request.url.params),
                body=body,
            )
        )
        assert self.responses, f"unexpected extra request {request.method} {request.url}"
        return self.responses.pop(0)


def _install(monkeypatch, module, responses) -> FakeHttp:
    fake = FakeHttp(list(responses))

    class _MockedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            fake.client_kwargs.append(dict(kwargs))
            kwargs["transport"] = httpx.MockTransport(fake.handler)
            super().__init__(*args, **kwargs)

    namespace = types.SimpleNamespace(**{name: getattr(httpx, name) for name in dir(httpx) if not name.startswith("__")})
    namespace.AsyncClient = _MockedAsyncClient
    monkeypatch.setattr(module, "httpx", namespace)
    return fake


def _basic(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


@dataclass(frozen=True)
class Connector:
    name: str
    fetch: str
    error: str
    rate_error: str
    flag: str
    credentials: dict
    call: dict

    @property
    def module(self):
        return importlib.import_module(f"api.services.{self.name}_extraction")


CONNECTORS = [
    Connector("activecampaign", "fetch_activecampaign_contacts", "ActiveCampaignError", "ActiveCampaignRateLimitError", "ACTIVECAMPAIGN_ENABLED",
              {"ACTIVECAMPAIGN_API_TOKEN": "ac-test-token", "ACTIVECAMPAIGN_ACCOUNT": "acme"}, {}),
    Connector("airtable", "fetch_airtable_records", "AirtableError", "AirtableRateLimitError", "AIRTABLE_ENABLED",
              {"AIRTABLE_API_TOKEN": "pat-test-token"}, {"base_id": "appBASE1", "table_name": "Customers"}),
    Connector("asana", "fetch_asana_tasks", "AsanaError", "AsanaRateLimitError", "ASANA_ENABLED", {"ASANA_API_TOKEN": "asana-test-token"}, {}),
    Connector("box", "fetch_box_files", "BoxError", "BoxRateLimitError", "BOX_ENABLED", {"BOX_API_TOKEN": "box-test-token"}, {}),
    Connector("clickup", "fetch_clickup_tasks", "ClickUpError", "ClickUpRateLimitError", "CLICKUP_ENABLED",
              {"CLICKUP_API_TOKEN": "pk_test_token"}, {"list_id": "L-900"}),
    Connector("docusign", "fetch_docusign_envelopes", "DocuSignError", "DocuSignRateLimitError", "DOCUSIGN_ENABLED",
              {"DOCUSIGN_API_TOKEN": "ds-test-token", "DOCUSIGN_ACCOUNT_ID": "acct-42"}, {}),
    Connector("dropbox", "fetch_dropbox_files", "DropboxError", "DropboxRateLimitError", "DROPBOX_ENABLED", {"DROPBOX_API_TOKEN": "dbx-test-token"}, {}),
    Connector("hive", "fetch_hive_actions", "HiveError", "HiveRateLimitError", "HIVE_ENABLED", {"HIVE_API_TOKEN": "hive-test-token"}, {"workspace_id": "W1"}),
    Connector("hubspot", "fetch_hubspot_records", "HubSpotError", "HubSpotRateLimitError", "HUBSPOT_ENABLED", {"HUBSPOT_API_TOKEN": "hs-test-token"}, {}),
    Connector("intercom", "fetch_intercom_conversations", "IntercomError", "IntercomRateLimitError", "INTERCOM_ENABLED",
              {"INTERCOM_API_TOKEN": "ic-test-token"}, {}),
    Connector("jira", "fetch_jira_issues", "JiraError", "JiraRateLimitError", "JIRA_ENABLED",
              {"JIRA_BASE_URL": "https://acme.atlassian.net", "JIRA_EMAIL": "ada@acme.example", "JIRA_API_TOKEN": "jira-test-token"}, {}),
    Connector("klaviyo", "fetch_klaviyo_profiles", "KlaviyoError", "KlaviyoRateLimitError", "KLAVIYO_ENABLED", {"KLAVIYO_API_TOKEN": "pk_klaviyo_test"}, {}),
    Connector("linear", "fetch_linear_issues", "LinearError", "LinearRateLimitError", "LINEAR_ENABLED", {"LINEAR_API_TOKEN": "lin_api_test"}, {}),
    Connector("mailchimp", "fetch_mailchimp_audiences", "MailchimpError", "MailchimpRateLimitError", "MAILCHIMP_ENABLED",
              {"MAILCHIMP_API_TOKEN": "mc-test-token-us21", "MAILCHIMP_DC": "us21"}, {}),
    Connector("nifty", "fetch_nifty_tasks", "NiftyError", "NiftyRateLimitError", "NIFTY_ENABLED", {"NIFTY_API_TOKEN": "nifty-test-token"}, {"project_id": "P1"}),
    Connector("pipedrive", "fetch_pipedrive_records", "PipedriveError", "PipedriveRateLimitError", "PIPEDRIVE_ENABLED",
              {"PIPEDRIVE_API_TOKEN": "pd-test-token"}, {}),
    Connector("pipefy", "fetch_pipefy_cards", "PipefyError", "PipefyRateLimitError", "PIPEFY_ENABLED", {"PIPEFY_API_TOKEN": "pipefy-test-token"}, {"pipe_id": "301"}),
    Connector("podio", "fetch_podio_items", "PodioError", "PodioRateLimitError", "PODIO_ENABLED", {"PODIO_API_TOKEN": "podio-test-token"}, {"app_id": "555"}),
    Connector("process_street", "fetch_process_street_workflows", "ProcessStreetError", "ProcessStreetRateLimitError", "PROCESS_STREET_ENABLED",
              {"PROCESS_STREET_API_TOKEN": "ps-test-token"}, {}),
    Connector("salesforce", "fetch_salesforce_records", "SalesforceError", "SalesforceRateLimitError", "SALESFORCE_ENABLED",
              {"SALESFORCE_CLIENT_ID": "sf-client-id", "SALESFORCE_CLIENT_SECRET": "sf-client-secret"}, {}),
    Connector("shopify", "fetch_shopify_orders", "ShopifyError", "ShopifyRateLimitError", "SHOPIFY_ENABLED",
              {"SHOPIFY_API_TOKEN": "shpat_test", "SHOPIFY_SHOP_DOMAIN": "acme.myshopify.com"}, {}),
    Connector("smartsuite", "fetch_smartsuite_records", "SmartSuiteError", "SmartSuiteRateLimitError", "SMARTSUITE_ENABLED",
              {"SMARTSUITE_API_TOKEN": "ss-test-token", "SMARTSUITE_ACCOUNT_ID": "ws-77"}, {"table_id": "tbl-1"}),
    Connector("teamwork", "fetch_teamwork_tasks", "TeamworkError", "TeamworkRateLimitError", "TEAMWORK_ENABLED",
              {"TEAMWORK_API_TOKEN": "tw-test-token", "TEAMWORK_DOMAIN": "acme"}, {}),
    Connector("trello", "fetch_trello_cards", "TrelloError", "TrelloRateLimitError", "TRELLO_ENABLED",
              {"TRELLO_API_KEY": "trello-test-key", "TRELLO_API_TOKEN": "trello-test-token"}, {"board_id": "B1"}),
    Connector("woocommerce", "fetch_woocommerce_orders", "WooCommerceError", "WooCommerceRateLimitError", "WOOCOMMERCE_ENABLED",
              {"WOOCOMMERCE_API_TOKEN": "ck_test:cs_test", "WOOCOMMERCE_STORE_URL": "https://shop.acme.test"}, {}),
    Connector("zendesk", "fetch_zendesk_tickets", "ZendeskError", "ZendeskRateLimitError", "ZENDESK_ENABLED",
              {"ZENDESK_SUBDOMAIN": "acme", "ZENDESK_EMAIL": "ada@acme.example", "ZENDESK_API_TOKEN": "zd-test-token"}, {}),
    Connector("zoho", "fetch_zoho_records", "ZohoError", "ZohoRateLimitError", "ZOHO_ENABLED", {"ZOHO_API_TOKEN": "zoho-test-token"}, {}),
]
BY_NAME = {c.name: c for c in CONNECTORS}
# these loop over several object types and only log a non-429 failure (covered by dedicated tests below)
LOG_AND_CONTINUE = {"hubspot", "pipedrive"}
MISSING_CREDENTIAL_CASES = [(c, name) for c in CONNECTORS for name in c.credentials]


@pytest.fixture(autouse=True)
def _outside_any_organization_scope():
    """The fallback to api.config.settings only exists outside connector_scope; make sure no scope leaked into these tests."""
    assert connector_credentials._active.get() is None


def _configure(monkeypatch, connector: Connector, *, enabled=True, blank=None, extra=None):
    monkeypatch.setattr(settings, connector.flag, enabled)
    for name, value in connector.credentials.items():
        monkeypatch.setattr(settings, name, "" if name == blank else value)
    for name, value in (extra or {}).items():
        monkeypatch.setattr(settings, name, value)


async def _run(connector: Connector, **overrides):
    return await getattr(connector.module, connector.fetch)(**{**connector.call, **overrides})


def _ok(payload) -> httpx.Response:
    return httpx.Response(200, json=payload)


# ------------------------------------------------------------------ guards: nothing is sent


@pytest.mark.parametrize("connector", CONNECTORS, ids=[c.name for c in CONNECTORS])
async def test_a_disabled_connector_raises_its_error_and_sends_nothing(monkeypatch, connector):
    _configure(monkeypatch, connector, enabled=False)
    fake = _install(monkeypatch, connector.module, [])

    with pytest.raises(getattr(connector.module, connector.error), match="integration is disabled") as caught:
        await _run(connector)

    assert type(caught.value) is getattr(connector.module, connector.error)
    assert fake.requests == []


@pytest.mark.parametrize(("connector", "missing"), MISSING_CREDENTIAL_CASES, ids=[f"{c.name}-{n}" for c, n in MISSING_CREDENTIAL_CASES])
async def test_a_missing_credential_raises_its_error_and_sends_nothing(monkeypatch, connector, missing):
    _configure(monkeypatch, connector, blank=missing)
    fake = _install(monkeypatch, connector.module, [])

    with pytest.raises(getattr(connector.module, connector.error), match="not configured") as caught:
        await _run(connector)

    assert type(caught.value) is getattr(connector.module, connector.error)
    assert fake.requests == []


# ------------------------------------------------------------------ error statuses


@pytest.mark.parametrize("connector", CONNECTORS, ids=[c.name for c in CONNECTORS])
async def test_429_raises_the_rate_limit_error_which_is_a_module_error(monkeypatch, connector):
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [httpx.Response(429, json={"message": "slow down"})])

    with pytest.raises(getattr(connector.module, connector.rate_error), match="rate limit reached") as caught:
        await _run(connector)

    assert isinstance(caught.value, getattr(connector.module, connector.error))
    assert len(fake.requests) == 1, "a 429 must stop the import, not be retried or skipped"


SINGLE_FAILURE = [c for c in CONNECTORS if c.name not in LOG_AND_CONTINUE]


@pytest.mark.parametrize("connector", SINGLE_FAILURE, ids=[c.name for c in SINGLE_FAILURE])
async def test_500_raises_the_module_error_with_the_status(monkeypatch, connector):
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [httpx.Response(500, json={"message": "boom"})])

    with pytest.raises(getattr(connector.module, connector.error), match=r"failed: 500$") as caught:
        await _run(connector)

    assert type(caught.value) is getattr(connector.module, connector.error), "a 500 is not a rate limit"
    assert len(fake.requests) == 1


async def test_hubspot_logs_a_failed_object_type_and_keeps_the_others(monkeypatch, caplog):
    connector = BY_NAME["hubspot"]
    _configure(monkeypatch, connector, extra={"HUBSPOT_API_BASE_URL": "https://api.hubapi.com"})
    fake = _install(monkeypatch, connector.module, [
        httpx.Response(500, json={"message": "boom"}),
        _ok({"results": [{"id": "901", "properties": {"name": "Renewal deal"}}]}),
    ])
    caplog.set_level(logging.WARNING, logger="api.services.hubspot_extraction")

    records = await _run(connector, object_types=["contacts", "deals"])

    assert [r.path for r in fake.requests] == ["/crm/v3/objects/contacts", "/crm/v3/objects/deals"]
    assert records == [{"object_type": "deals", "id": "901", "properties": {"name": "Renewal deal"}, "text": "deals 901\nname: Renewal deal"}]
    warnings = [r for r in caplog.records if r.name == "api.services.hubspot_extraction"]
    assert [(r.levelno, r.getMessage()) for r in warnings] == [(logging.WARNING, "HubSpot fetch failed for contacts: 500")]


async def test_hubspot_429_on_a_later_object_type_stops_the_import(monkeypatch):
    connector = BY_NAME["hubspot"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"results": [{"id": "1", "properties": {}}]}), httpx.Response(429)])

    with pytest.raises(connector.module.HubSpotRateLimitError, match="rate limit reached on companies"):
        await _run(connector, object_types=["contacts", "companies", "deals"])

    assert len(fake.requests) == 2


async def test_pipedrive_logs_a_failed_object_type_and_keeps_the_others(monkeypatch, caplog):
    connector = BY_NAME["pipedrive"]
    _configure(monkeypatch, connector, extra={"PIPEDRIVE_API_BASE_URL": "https://api.pipedrive.com/v1"})
    fake = _install(monkeypatch, connector.module, [
        _ok({"data": [{"id": 7, "title": "Big deal"}]}),
        httpx.Response(503, text="maintenance"),
    ])
    caplog.set_level(logging.WARNING, logger="api.services.pipedrive_extraction")

    records = await _run(connector, objects=["deals", "persons"])

    assert [r.path for r in fake.requests] == ["/v1/deals", "/v1/persons"]
    assert [(r["object_type"], r["id"], r["text"]) for r in records] == [("deals", 7, "deals 7\nid: 7\ntitle: Big deal")]
    warnings = [r for r in caplog.records if r.name == "api.services.pipedrive_extraction"]
    assert [(r.levelno, r.getMessage()) for r in warnings] == [(logging.WARNING, "Pipedrive fetch failed for persons: 503")]


async def test_salesforce_auth_failure_raises_before_any_object_is_fetched(monkeypatch):
    connector = BY_NAME["salesforce"]
    _configure(monkeypatch, connector, extra={"SALESFORCE_INSTANCE_URL": "https://acme.my.salesforce.com"})
    fake = _install(monkeypatch, connector.module, [httpx.Response(401, json={"error": "invalid_client"})])

    with pytest.raises(connector.module.SalesforceError, match="Salesforce auth failed: 401"):
        await _run(connector)

    assert [(r.method, r.path) for r in fake.requests] == [("POST", "/services/oauth2/token")]


async def test_salesforce_logs_a_failed_object_and_429_on_an_object_stops_the_import(monkeypatch, caplog):
    connector = BY_NAME["salesforce"]
    _configure(monkeypatch, connector, extra={"SALESFORCE_INSTANCE_URL": "https://acme.my.salesforce.com"})
    fake = _install(monkeypatch, connector.module, [
        _ok({"access_token": "sf-access-token"}),
        httpx.Response(500, json={"message": "boom"}),
        httpx.Response(429),
    ])
    caplog.set_level(logging.WARNING, logger="api.services.salesforce_extraction")

    with pytest.raises(connector.module.SalesforceRateLimitError, match="rate limit reached on Account"):
        await _run(connector, sobjects=["Contact", "Account", "Lead"])

    assert len(fake.requests) == 3
    assert all(r.headers["authorization"] == "Bearer sf-access-token" for r in fake.requests[1:])
    warnings = [r for r in caplog.records if r.name == "api.services.salesforce_extraction"]
    assert [(r.levelno, r.getMessage()) for r in warnings] == [(logging.WARNING, "Salesforce fetch failed for Contact: 500")]


async def test_salesforce_returns_nothing_when_every_object_fails(monkeypatch, caplog):
    connector = BY_NAME["salesforce"]
    _configure(monkeypatch, connector, extra={"SALESFORCE_INSTANCE_URL": "https://acme.my.salesforce.com"})
    _install(monkeypatch, connector.module, [_ok({"access_token": "t"}), httpx.Response(500), httpx.Response(404)])
    caplog.set_level(logging.WARNING, logger="api.services.salesforce_extraction")

    assert await _run(connector, sobjects=["Contact", "Lead"]) == []
    assert [r.getMessage() for r in caplog.records if r.name == "api.services.salesforce_extraction"] == [
        "Salesforce fetch failed for Contact: 500",
        "Salesforce fetch failed for Lead: 404",
    ]


# ------------------------------------------------------------------ GraphQL body-level errors


@pytest.mark.parametrize("name", ["linear", "pipefy"])
async def test_a_graphql_error_body_raises_the_module_error(monkeypatch, name):
    connector = BY_NAME[name]
    _configure(monkeypatch, connector)
    _install(monkeypatch, connector.module, [_ok({"errors": [{"message": "Field 'x' doesn't exist"}], "data": None})])

    with pytest.raises(getattr(connector.module, connector.error), match="GraphQL errors: .*Field 'x' doesn't exist") as caught:
        await _run(connector)

    assert type(caught.value) is getattr(connector.module, connector.error)


# ------------------------------------------------------------------ success: request shape and records


async def test_activecampaign_contacts(monkeypatch):
    connector = BY_NAME["activecampaign"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"contacts": [
        {"id": "11", "email": "ada@acme.test", "firstName": "Ada", "lastName": "Lovelace", "phone": "+33 1 23 45"},
        {"id": "12", "email": "bob@acme.test", "firstName": "", "phone": None},
    ]})])

    records = await _run(connector, limit=250)

    (request,) = fake.requests
    assert (request.method, request.url) == ("GET", "https://acme.api-us1.com/api/3/contacts?limit=100")
    assert request.headers["api-token"] == "ac-test-token"
    assert "authorization" not in request.headers
    assert records == [
        {"id": "11", "email": "ada@acme.test", "text": "Contact: ada@acme.test\nID: 11\nFirst name: Ada\nLast name: Lovelace\nPhone: +33 1 23 45"},
        {"id": "12", "email": "bob@acme.test", "text": "Contact: bob@acme.test\nID: 12"},
    ]


async def test_airtable_records(monkeypatch):
    connector = BY_NAME["airtable"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"records": [
        {"id": "rec1", "fields": {"Name": "Acme", "Notes": "Renewal in March", "Empty": "", "Missing": None, "Seats": 12}},
        {"id": "rec2"},
    ]})])

    records = await _run(connector, limit=7)

    (request,) = fake.requests
    assert (request.method, request.url) == ("GET", "https://api.airtable.com/v0/appBASE1/Customers?maxRecords=7")
    assert request.headers["authorization"] == "Bearer pat-test-token"
    assert records[0]["id"] == "rec1"
    assert records[0]["text"] == "Record: rec1\nName: Acme\nNotes: Renewal in March\nSeats: 12"
    assert records[0]["fields"]["Seats"] == 12
    assert records[1] == {"id": "rec2", "fields": {}, "text": "Record: rec2"}


async def test_box_keeps_only_files(monkeypatch):
    connector = BY_NAME["box"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"entries": [
        {"type": "file", "id": "f1", "name": "contract.pdf"},
        {"type": "folder", "id": "d1", "name": "Archive"},
        {"type": "web_link", "id": "w1", "name": "Wiki"},
        {"type": "file", "id": "f2", "name": "notes.docx"},
    ]})])

    records = await _run(connector, folder_id="98765", limit=3)

    (request,) = fake.requests
    assert (request.method, request.url) == ("GET", "https://api.box.com/2.0/folders/98765/items?limit=3")
    assert request.headers["authorization"] == "Bearer box-test-token"
    assert records == [
        {"id": "f1", "name": "contract.pdf", "text": "File: contract.pdf\nID: f1"},
        {"id": "f2", "name": "notes.docx", "text": "File: notes.docx\nID: f2"},
    ]


async def test_clickup_tasks(monkeypatch):
    connector = BY_NAME["clickup"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"tasks": [
        {"id": "t1", "name": "Ship v2", "description": "Release notes", "status": {"status": "in progress"}, "priority": {"priority": "urgent"}},
        {"id": "t2", "name": "Write docs", "description": "", "status": None, "priority": None},
        {"id": "t3", "name": "Beyond the limit"},
    ]})])

    records = await _run(connector, limit=2)

    (request,) = fake.requests
    assert (request.method, request.url) == ("GET", "https://api.clickup.com/api/v2/list/L-900/task?page=0")
    assert request.headers["authorization"] == "pk_test_token", "ClickUp takes the raw token, no Bearer prefix"
    assert records == [
        {"id": "t1", "name": "Ship v2", "text": "Task: Ship v2\nID: t1\nDescription: Release notes\nStatus: in progress\nPriority: urgent"},
        {"id": "t2", "name": "Write docs", "text": "Task: Write docs\nID: t2"},
    ]


async def test_docusign_envelopes(monkeypatch):
    connector = BY_NAME["docusign"]
    _configure(monkeypatch, connector, extra={"DOCUSIGN_BASE_URL": "https://demo.docusign.net/"})
    fake = _install(monkeypatch, connector.module, [_ok({"envelopes": [
        {"envelopeId": "env-1", "emailSubject": "Please sign the NDA", "status": "completed", "createdDateTime": "2026-01-02T10:00:00Z"},
    ]})])

    records = await _run(connector, limit=500)

    (request,) = fake.requests
    assert (request.method, request.host, request.path) == ("GET", "demo.docusign.net", "/restapi/v2.1/accounts/acct-42/envelopes")
    assert request.params == {"from_date": "2020-01-01", "count": "100"}
    assert request.headers["authorization"] == "Bearer ds-test-token"
    assert records == [{
        "id": "env-1",
        "text": "Envelope: env-1\nSubject: Please sign the NDA\nStatus: completed\nCreated: 2026-01-02T10:00:00Z",
    }]


async def test_dropbox_lists_a_folder_and_keeps_only_files(monkeypatch):
    connector = BY_NAME["dropbox"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"entries": [
        {".tag": "file", "id": "id:a1", "name": "plan.md", "path_display": "/Contracts/plan.md", "size": 2048},
        {".tag": "folder", "id": "id:d1", "name": "old", "path_display": "/Contracts/old"},
        {".tag": "deleted", "name": "gone.txt", "path_display": "/Contracts/gone.txt"},
    ]})])

    records = await _run(connector, path="/Contracts", limit=25)

    (request,) = fake.requests
    assert (request.method, request.url) == ("POST", "https://api.dropboxapi.com/2/files/list_folder")
    assert request.body == {"path": "/Contracts", "limit": 25}
    assert request.headers["authorization"] == "Bearer dbx-test-token"
    assert records == [{"id": "id:a1", "name": "plan.md", "path": "/Contracts/plan.md", "text": "File: plan.md\nPath: /Contracts/plan.md\nSize: 2048"}]


async def test_hubspot_records_per_object_type(monkeypatch):
    connector = BY_NAME["hubspot"]
    _configure(monkeypatch, connector, extra={"HUBSPOT_API_BASE_URL": "https://api.hubapi.com"})
    fake = _install(monkeypatch, connector.module, [
        _ok({"results": [{"id": "101", "properties": {"firstname": "Ada", "lastname": "Lovelace", "email": "", "phone": None}}]}),
        _ok({"results": [{"id": "202", "properties": None}]}),
    ])

    records = await _run(connector, object_types=["contacts", "tickets"], limit=5)

    assert [(r.method, r.host, r.path) for r in fake.requests] == [
        ("GET", "api.hubapi.com", "/crm/v3/objects/contacts"),
        ("GET", "api.hubapi.com", "/crm/v3/objects/tickets"),
    ]
    for request in fake.requests:
        assert request.headers["authorization"] == "Bearer hs-test-token"
        assert request.params == {"limit": "5", "properties": "firstname,lastname,email,name,description,phone,company"}
    assert records == [
        {"object_type": "contacts", "id": "101", "properties": {"firstname": "Ada", "lastname": "Lovelace", "email": "", "phone": None},
         "text": "contacts 101\nfirstname: Ada\nlastname: Lovelace"},
        {"object_type": "tickets", "id": "202", "properties": {}, "text": "tickets 202"},
    ]


async def test_hubspot_defaults_to_the_four_crm_object_types(monkeypatch):
    connector = BY_NAME["hubspot"]
    _configure(monkeypatch, connector, extra={"HUBSPOT_API_BASE_URL": "https://api.hubapi.com"})
    fake = _install(monkeypatch, connector.module, [_ok({"results": []}) for _ in range(4)])

    assert await _run(connector) == []
    assert [r.path.rsplit("/", 1)[1] for r in fake.requests] == ["contacts", "companies", "deals", "tickets"]


async def test_intercom_conversations(monkeypatch):
    connector = BY_NAME["intercom"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"conversations": [
        {"id": "c1", "created_at": 1700000000, "source": {"subject": "Refund request"}},
        {"id": "c2", "created_at": 1700000100},
    ]})])

    records = await _run(connector, limit=500)

    (request,) = fake.requests
    assert (request.method, request.url) == ("GET", "https://api.intercom.io/conversations?per_page=150")
    assert request.headers["authorization"] == "Bearer ic-test-token"
    assert request.headers["intercom-version"] == "2.10"
    assert records == [
        {"id": "c1", "text": "Conversation: c1\nCreated: 1700000000\nSource: Refund request"},
        {"id": "c2", "text": "Conversation: c2\nCreated: 1700000100"},
    ]


async def test_klaviyo_profiles(monkeypatch):
    connector = BY_NAME["klaviyo"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"data": [
        {"id": "01P1", "attributes": {"email": "ada@acme.test", "first_name": "Ada", "last_name": "Lovelace", "phone_number": "+33123"}},
        {"id": "01P2", "attributes": None},
    ]})])

    records = await _run(connector, limit=40)

    (request,) = fake.requests
    assert (request.method, request.host, request.path) == ("GET", "a.klaviyo.com", "/api/profiles")
    assert request.params == {"page[size]": "40"}
    assert request.headers["authorization"] == "Klaviyo-API-Key pk_klaviyo_test"
    assert request.headers["revision"] == "2024-10-15"
    assert records == [
        {"id": "01P1", "email": "ada@acme.test", "text": "Profile: 01P1\nEmail: ada@acme.test\nFirst name: Ada\nLast name: Lovelace\nPhone: +33123"},
        {"id": "01P2", "email": None, "text": "Profile: 01P2"},
    ]


async def test_klaviyo_caps_the_page_size_at_100(monkeypatch):
    connector = BY_NAME["klaviyo"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"data": []})])

    assert await _run(connector, limit=1000) == []
    assert fake.requests[0].params == {"page[size]": "100"}


async def test_linear_issues(monkeypatch):
    connector = BY_NAME["linear"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"data": {"issues": {"nodes": [
        {"id": "uuid-1", "identifier": "ENG-12", "title": "Login fails", "description": "Steps to reproduce", "state": {"name": "Todo"},
         "priority": 0, "assignee": {"name": "Ada"}, "team": {"name": "Engineering", "key": "ENG"}},
        {"id": "uuid-2", "identifier": "ENG-13", "title": "Typo", "description": None, "state": None, "priority": None, "assignee": None, "team": None},
    ]}}})])

    records = await _run(connector, limit=20)

    (request,) = fake.requests
    assert (request.method, request.url) == ("POST", "https://api.linear.app/graphql")
    assert request.headers["authorization"] == "lin_api_test", "a Linear personal key is sent raw"
    assert request.body["variables"] == {"first": 20}
    assert "issues(first: $first)" in request.body["query"]
    assert records == [
        {"id": "uuid-1", "identifier": "ENG-12", "title": "Login fails",
         "text": "Identifier: ENG-12\nTitle: Login fails\nDescription: Steps to reproduce\nState: Todo\nPriority: 0\nAssignee: Ada\nTeam: Engineering"},
        {"id": "uuid-2", "identifier": "ENG-13", "title": "Typo", "text": "Identifier: ENG-13\nTitle: Typo"},
    ]


async def test_mailchimp_audiences(monkeypatch):
    connector = BY_NAME["mailchimp"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"lists": [
        {"id": "L1", "name": "Customers", "stats": {"member_count": 42}},
        {"id": "L2", "name": "Prospects"},
    ]})])

    records = await _run(connector, limit=300)

    (request,) = fake.requests
    assert (request.method, request.url) == ("GET", "https://us21.api.mailchimp.com/3.0/lists?count=100")
    assert request.headers["authorization"] == _basic("anystring", "mc-test-token-us21")
    assert records == [
        {"id": "L1", "name": "Customers", "text": "Audience: Customers\nID: L1\nMembers: 42"},
        {"id": "L2", "name": "Prospects", "text": "Audience: Prospects\nID: L2"},
    ]


async def test_pipedrive_records_skip_nested_and_empty_values(monkeypatch):
    connector = BY_NAME["pipedrive"]
    _configure(monkeypatch, connector, extra={"PIPEDRIVE_API_BASE_URL": "https://api.pipedrive.com/v1"})
    deal = {"id": 7, "title": "Big deal", "value": 5000, "org_id": {"name": "Acme"}, "labels": [1, 2], "notes": "", "lost_reason": None}
    fake = _install(monkeypatch, connector.module, [_ok({"data": [deal]}), _ok({"data": None})])

    records = await _run(connector, objects=["deals", "persons"], limit=15)

    assert [(r.method, r.host, r.path) for r in fake.requests] == [("GET", "api.pipedrive.com", "/v1/deals"), ("GET", "api.pipedrive.com", "/v1/persons")]
    assert all(r.params == {"api_token": "pd-test-token", "limit": "15"} for r in fake.requests)
    assert all("authorization" not in r.headers for r in fake.requests)
    assert records == [{"object_type": "deals", "id": 7, "fields": deal, "text": "deals 7\nid: 7\ntitle: Big deal\nvalue: 5000"}]


async def test_podio_items_keep_only_scalar_values(monkeypatch):
    connector = BY_NAME["podio"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"items": [
        {"item_id": 9001, "fields": [
            {"label": "Title", "values": [{"value": "Kickoff"}]},
            {"label": "Owner", "values": [{"value": {"name": "Ada"}}]},
            {"label": "Notes", "values": [{"value": ""}]},
            {"label": "Budget", "values": [{"value": 1200}, "not-a-dict"]},
        ]},
        {"item_id": 9002},
    ]})])

    records = await _run(connector, limit=10)

    (request,) = fake.requests
    assert (request.method, request.url) == ("POST", "https://api.podio.com/item/app/555/filter/")
    assert request.body == {"limit": 10}
    assert request.headers["authorization"] == "OAuth2 podio-test-token"
    assert records == [
        {"id": 9001, "text": "Item: 9001\nTitle: Kickoff\nBudget: 1200"},
        {"id": 9002, "text": "Item: 9002"},
    ]


async def test_shopify_orders(monkeypatch):
    connector = BY_NAME["shopify"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"orders": [
        {"id": 450789469, "order_number": 1001, "total_price": "199.00", "currency": "EUR", "created_at": "2026-03-01T09:00:00Z", "email": "ada@acme.test"},
        {"id": 450789470, "order_number": 1002, "total_price": "5.00", "currency": "EUR", "created_at": "2026-03-02T09:00:00Z", "email": None},
    ]})])

    records = await _run(connector, limit=1000)

    (request,) = fake.requests
    assert (request.method, request.url) == ("GET", "https://acme.myshopify.com/admin/api/2024-01/orders.json?limit=250")
    assert request.headers["x-shopify-access-token"] == "shpat_test"
    assert records == [
        {"id": 450789469, "text": "Order #1001\nTotal: 199.00 EUR\nCreated: 2026-03-01T09:00:00Z\nEmail: ada@acme.test"},
        {"id": 450789470, "text": "Order #1002\nTotal: 5.00 EUR\nCreated: 2026-03-02T09:00:00Z"},
    ]


async def test_smartsuite_records(monkeypatch):
    # Where `limit` travels is deliberately not asserted: the module puts it in the JSON body, SmartSuite documents it as a query parameter.
    connector = BY_NAME["smartsuite"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"items": [
        {"id": "rec-1", "title": "Onboarding", "status": {"value": "done"}, "tags": ["a"], "notes": "", "owner": None, "score": 4},
    ]})])

    records = await _run(connector)

    (request,) = fake.requests
    assert (request.method, request.host, request.path) == ("POST", "app.smartsuite.com", "/api/v1/applications/tbl-1/records/list/")
    assert request.headers["authorization"] == "Token ss-test-token"
    assert request.headers["account-id"] == "ws-77"
    assert records == [{"id": "rec-1", "text": "Record: rec-1\nid: rec-1\ntitle: Onboarding\nscore: 4"}]


async def test_trello_cards_use_query_credentials_and_the_limit(monkeypatch):
    connector = BY_NAME["trello"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok([
        {"id": "c1", "name": "Plan sprint", "desc": "Pick stories", "due": "2026-04-01T00:00:00Z", "closed": False},
        {"id": "c2", "name": "Retro", "desc": "", "due": None},
        {"id": "c3", "name": "Beyond the limit"},
    ])])

    records = await _run(connector, limit=2)

    (request,) = fake.requests
    assert (request.method, request.host, request.path) == ("GET", "api.trello.com", "/1/boards/B1/cards")
    assert request.params == {"key": "trello-test-key", "token": "trello-test-token"}
    assert "authorization" not in request.headers
    assert records == [
        {"id": "c1", "name": "Plan sprint", "text": "Card: Plan sprint\nID: c1\nDescription: Pick stories\nDue: 2026-04-01T00:00:00Z\nClosed: False"},
        {"id": "c2", "name": "Retro", "text": "Card: Retro\nID: c2"},
    ]


async def test_woocommerce_orders(monkeypatch):
    connector = BY_NAME["woocommerce"]
    _configure(monkeypatch, connector, extra={"WOOCOMMERCE_STORE_URL": "https://shop.acme.test/"})
    fake = _install(monkeypatch, connector.module, [_ok([
        {"id": 727, "number": "727", "total": "49.90", "currency": "EUR", "status": "processing"},
    ])])

    records = await _run(connector, limit=150)

    (request,) = fake.requests
    assert (request.method, request.url) == ("GET", "https://shop.acme.test/wp-json/wc/v3/orders?per_page=100")
    assert request.headers["authorization"] == _basic("ck_test", "cs_test")
    assert records == [{"id": 727, "text": "Order #727\nTotal: 49.90 EUR\nStatus: processing"}]


async def test_zoho_records(monkeypatch):
    connector = BY_NAME["zoho"]
    _configure(monkeypatch, connector)
    fake = _install(monkeypatch, connector.module, [_ok({"data": [
        {"id": "z1", "Last_Name": "Lovelace", "Company": "Acme", "Owner": {"name": "Bob"}, "Tag": [], "Email": None, "Phone": ""},
    ]})])

    records = await _run(connector, module="Contacts", limit=500)

    (request,) = fake.requests
    assert (request.method, request.url) == ("GET", "https://www.zohoapis.com/crm/v2/Contacts?per_page=200")
    assert request.headers["authorization"] == "Zoho-oauthtoken zoho-test-token"
    assert records == [{"id": "z1", "text": "Record: z1\nid: z1\nLast_Name: Lovelace\nCompany: Acme"}]


def test_every_connector_in_scope_is_covered_and_the_dead_ones_are_not():
    covered = {c.name for c in CONNECTORS}
    assert len(covered) == 27
    assert covered.isdisjoint({"azure_devops", "basecamp", "bitbucket", "coda", "gitlab", "miro", "monday", "smartsheet", "wrike"})
    for connector in CONNECTORS:
        module = connector.module
        assert issubclass(getattr(module, connector.rate_error), getattr(module, connector.error))
        assert callable(getattr(module, connector.fetch))
