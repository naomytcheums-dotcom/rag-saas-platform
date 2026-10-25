"""CRM import routes (api/routers/crm.py): what an import actually leaves in the knowledge base.

tests/test_crm_endpoints.py covers authentication, the disabled flag and RBAC. Here the provider's fetch function is replaced (no network, no
credential) and every one of the 36 routes is driven end to end: the records it returns must become documents of THIS organization that
survive the end of the request. `get_db` never commits, it only closes the session, which rolls back whatever was not committed: the tests
reproduce that with `db_session.rollback()` before counting, so a route that only flushes is caught.
"""

import importlib
import uuid

import pytest
from sqlalchemy import func, select

from api.config import settings
from api.models.document import Document
from api.models.user import User

# provider (URL segment), extraction module, error class, fetch function, settings flag
PROVIDERS = [
    ("salesforce", "salesforce_extraction", "SalesforceError", "fetch_salesforce_records", "SALESFORCE_ENABLED"),
    ("hubspot", "hubspot_extraction", "HubSpotError", "fetch_hubspot_records", "HUBSPOT_ENABLED"),
    ("jira", "jira_extraction", "JiraError", "fetch_jira_issues", "JIRA_ENABLED"),
    ("zendesk", "zendesk_extraction", "ZendeskError", "fetch_zendesk_tickets", "ZENDESK_ENABLED"),
    ("pipedrive", "pipedrive_extraction", "PipedriveError", "fetch_pipedrive_records", "PIPEDRIVE_ENABLED"),
    ("linear", "linear_extraction", "LinearError", "fetch_linear_issues", "LINEAR_ENABLED"),
    ("asana", "asana_extraction", "AsanaError", "fetch_asana_tasks", "ASANA_ENABLED"),
    ("trello", "trello_extraction", "TrelloError", "fetch_trello_cards", "TRELLO_ENABLED"),
    ("airtable", "airtable_extraction", "AirtableError", "fetch_airtable_records", "AIRTABLE_ENABLED"),
    ("dropbox", "dropbox_extraction", "DropboxError", "fetch_dropbox_files", "DROPBOX_ENABLED"),
    ("box", "box_extraction", "BoxError", "fetch_box_files", "BOX_ENABLED"),
    ("clickup", "clickup_extraction", "ClickUpError", "fetch_clickup_tasks", "CLICKUP_ENABLED"),
    ("intercom", "intercom_extraction", "IntercomError", "fetch_intercom_conversations", "INTERCOM_ENABLED"),
    ("zoho", "zoho_extraction", "ZohoError", "fetch_zoho_records", "ZOHO_ENABLED"),
    ("shopify", "shopify_extraction", "ShopifyError", "fetch_shopify_orders", "SHOPIFY_ENABLED"),
    ("woocommerce", "woocommerce_extraction", "WooCommerceError", "fetch_woocommerce_orders", "WOOCOMMERCE_ENABLED"),
    ("docusign", "docusign_extraction", "DocuSignError", "fetch_docusign_envelopes", "DOCUSIGN_ENABLED"),
    ("monday", "monday_extraction", "MondaycomError", "fetch_monday_records", "MONDAY_ENABLED"),
    ("gitlab", "gitlab_extraction", "GitLabError", "fetch_gitlab_records", "GITLAB_ENABLED"),
    ("bitbucket", "bitbucket_extraction", "BitbucketError", "fetch_bitbucket_records", "BITBUCKET_ENABLED"),
    ("azure-devops", "azure_devops_extraction", "AzureDevOpsError", "fetch_azure_devops_records", "AZURE_DEVOPS_ENABLED"),
    ("basecamp", "basecamp_extraction", "BasecampError", "fetch_basecamp_records", "BASECAMP_ENABLED"),
    ("wrike", "wrike_extraction", "WrikeError", "fetch_wrike_records", "WRIKE_ENABLED"),
    ("smartsheet", "smartsheet_extraction", "SmartsheetError", "fetch_smartsheet_records", "SMARTSHEET_ENABLED"),
    ("coda", "coda_extraction", "CodaError", "fetch_coda_records", "CODA_ENABLED"),
    ("miro", "miro_extraction", "MiroError", "fetch_miro_records", "MIRO_ENABLED"),
    ("podio", "podio_extraction", "PodioError", "fetch_podio_items", "PODIO_ENABLED"),
    ("pipefy", "pipefy_extraction", "PipefyError", "fetch_pipefy_cards", "PIPEFY_ENABLED"),
    ("hive", "hive_extraction", "HiveError", "fetch_hive_actions", "HIVE_ENABLED"),
    ("teamwork", "teamwork_extraction", "TeamworkError", "fetch_teamwork_tasks", "TEAMWORK_ENABLED"),
    ("nifty", "nifty_extraction", "NiftyError", "fetch_nifty_tasks", "NIFTY_ENABLED"),
    ("smartsuite", "smartsuite_extraction", "SmartSuiteError", "fetch_smartsuite_records", "SMARTSUITE_ENABLED"),
    ("process-street", "process_street_extraction", "ProcessStreetError", "fetch_process_street_workflows", "PROCESS_STREET_ENABLED"),
    ("activecampaign", "activecampaign_extraction", "ActiveCampaignError", "fetch_activecampaign_contacts", "ACTIVECAMPAIGN_ENABLED"),
    ("mailchimp", "mailchimp_extraction", "MailchimpError", "fetch_mailchimp_audiences", "MAILCHIMP_ENABLED"),
    ("klaviyo", "klaviyo_extraction", "KlaviyoError", "fetch_klaviyo_profiles", "KLAVIYO_ENABLED"),
]
NEEDS_PROJECT_KEY = {"trello", "airtable", "clickup", "podio", "pipefy", "hive", "nifty", "smartsuite"}
PROVIDER_IDS = [p[0] for p in PROVIDERS]


async def test_the_table_lists_every_crm_import_route(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    exposed = sorted(p.split("/")[4] for p in paths if p.startswith("/organizations/{org_id}/crm/") and p.endswith("/import"))
    assert exposed == sorted(PROVIDER_IDS)


async def _owner_and_org(client, db_session, email):
    password = "correct-horse-battery-staple"
    token = (await client.post("/auth/register", json={"email": email, "password": password, "accept_terms": True})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org = (await client.post("/organizations", json={"name": f"CRM import {uuid.uuid4().hex[:6]}"}, headers=headers)).json()
    user = await db_session.scalar(select(User).where(User.email == email))
    return headers, uuid.UUID(org["id"]), user


@pytest.fixture
def stored_files(monkeypatch):
    """No S3: the object key is what the real uploader would return; `fail_on` makes the upload of matching filenames fail like an S3 outage."""
    state = {"keys": [], "fail_on": None}

    def fake_upload(org_id, doc_id, filename, content, content_type):
        if state["fail_on"] and state["fail_on"] in filename:
            raise RuntimeError("S3 unavailable")
        key = f"documents/{org_id}/{doc_id}/{filename}"
        state["keys"].append(key)
        return key

    monkeypatch.setattr("api.security.documents.upload_document_file", fake_upload)
    return state


def _install_fetch(monkeypatch, provider, outcome):
    _, module_name, error_name, fetch_name, flag = next(p for p in PROVIDERS if p[0] == provider)
    module = importlib.import_module(f"api.services.{module_name}")
    calls = []

    async def fake_fetch(**kwargs):
        calls.append(kwargs)
        if outcome == "error":
            raise getattr(module, error_name)(f"{provider} upstream refused the token")
        return outcome

    monkeypatch.setattr(module, fetch_name, fake_fetch)
    monkeypatch.setattr(settings, flag, True)
    return calls


async def _persisted(db_session, org_id):
    await db_session.rollback()  # what get_db's session close does to anything the route did not commit
    return list((await db_session.scalars(select(Document).where(Document.organization_id == org_id).order_by(Document.name))).all())


def _records(provider):
    return [
        {"id": "r1", "text": f"{provider} first record: renewal is due in March."},
        {"key": "K-2", "text": f"{provider} second record: the invoice was disputed."},
        {"id": "r3", "text": ""},  # nothing to ingest
        {"text": f"{provider} fourth record without an id."},
    ]


@pytest.mark.parametrize("provider", PROVIDER_IDS)
async def test_an_import_stores_every_record_with_text_as_a_document_of_the_caller_org(client, db_session, monkeypatch, stored_files, provider):
    headers, org_id, user = await _owner_and_org(client, db_session, f"crm-{provider}-{uuid.uuid4().hex[:6]}@example.com")
    calls = _install_fetch(monkeypatch, provider, _records(provider))

    response = await client.post(f"/organizations/{org_id}/crm/{provider}/import", json={"limit": 7, "project_key": "base1/table1"}, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"imported": 3, "source": provider, "status": "completed"}
    assert len(calls) == 1 and calls[0]["limit"] == 7
    documents = await _persisted(db_session, org_id)
    assert len(documents) == 3, "the route answered imported=3 but the documents did not survive the end of the request"
    names = [d.name for d in documents]
    for marker in ("-r1-", "-K-2-", "-3-"):  # id, then key, then the record's position
        assert sum(name.startswith(f"{provider}-") and marker in name for name in names) == 1, (marker, names)
    assert all(d.created_by == user.id and d.file_type == "text/plain" and d.file_key for d in documents)
    assert sorted(d.file_key for d in documents) == sorted(stored_files["keys"])


@pytest.mark.parametrize("provider", PROVIDER_IDS)
async def test_a_provider_error_is_a_502_and_stores_nothing(client, db_session, monkeypatch, stored_files, provider):
    headers, org_id, _ = await _owner_and_org(client, db_session, f"crm-err-{provider}-{uuid.uuid4().hex[:6]}@example.com")
    _install_fetch(monkeypatch, provider, "error")

    response = await client.post(f"/organizations/{org_id}/crm/{provider}/import", json={"project_key": "base1/table1"}, headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"] == f"{provider} upstream refused the token"
    assert await _persisted(db_session, org_id) == []
    assert stored_files["keys"] == []


@pytest.mark.parametrize("provider", sorted(NEEDS_PROJECT_KEY))
async def test_a_route_that_needs_a_project_key_refuses_to_call_the_provider_without_one(client, db_session, monkeypatch, stored_files, provider):
    headers, org_id, _ = await _owner_and_org(client, db_session, f"crm-pk-{provider}-{uuid.uuid4().hex[:6]}@example.com")
    calls = _install_fetch(monkeypatch, provider, _records(provider))

    response = await client.post(f"/organizations/{org_id}/crm/{provider}/import", json={"limit": 5}, headers=headers)

    assert response.status_code == 400
    assert "required" in response.json()["detail"]
    assert calls == []


async def test_airtable_needs_base_and_table(client, db_session, monkeypatch, stored_files):
    headers, org_id, _ = await _owner_and_org(client, db_session, f"crm-at-{uuid.uuid4().hex[:6]}@example.com")
    calls = _install_fetch(monkeypatch, "airtable", _records("airtable"))

    bad = await client.post(f"/organizations/{org_id}/crm/airtable/import", json={"project_key": "only-a-base"}, headers=headers)
    assert bad.status_code == 400 and calls == []

    good = await client.post(f"/organizations/{org_id}/crm/airtable/import", json={"project_key": "appXYZ/Leads/2024", "limit": 2}, headers=headers)
    assert good.status_code == 200
    assert calls == [{"base_id": "appXYZ", "table_name": "Leads/2024", "limit": 2}]


async def test_a_record_whose_upload_fails_is_skipped_without_leaving_a_half_created_document(client, db_session, monkeypatch, stored_files):
    headers, org_id, _ = await _owner_and_org(client, db_session, f"crm-s3-{uuid.uuid4().hex[:6]}@example.com")
    _install_fetch(monkeypatch, "hubspot", _records("hubspot"))
    stored_files["fail_on"] = "-K-2-"

    response = await client.post(f"/organizations/{org_id}/crm/hubspot/import", json={}, headers=headers)

    assert response.status_code == 200
    assert response.json()["imported"] == 2
    documents = await _persisted(db_session, org_id)
    assert len(documents) == 2
    assert all(d.file_key for d in documents), "a document row without its stored file was kept"
    assert not any("-K-2-" in d.name for d in documents)


async def test_an_import_never_writes_into_another_organization(client, db_session, monkeypatch, stored_files):
    headers, org_id, _ = await _owner_and_org(client, db_session, f"crm-iso-{uuid.uuid4().hex[:6]}@example.com")
    _, other_org_id, _ = await _owner_and_org(client, db_session, f"crm-iso2-{uuid.uuid4().hex[:6]}@example.com")
    _install_fetch(monkeypatch, "jira", _records("jira"))

    forbidden = await client.post(f"/organizations/{other_org_id}/crm/jira/import", json={}, headers=headers)
    assert forbidden.status_code in (403, 404)
    allowed = await client.post(f"/organizations/{org_id}/crm/jira/import", json={}, headers=headers)
    assert allowed.status_code == 200

    await db_session.rollback()
    assert await db_session.scalar(select(func.count()).select_from(Document).where(Document.organization_id == other_org_id)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Document).where(Document.organization_id == org_id)) == 3
