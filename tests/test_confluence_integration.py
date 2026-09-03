"""
Partie 2.1.17 -- orchestration tests for api/security/documents.py's own
import_and_process_confluence_page/process_confluence_space.

Same honest limitation as tests/test_confluence_extraction.py's own
module docstring, one level further: not even the mocked shapes here
could be checked against a real, live Confluence instance at all (see
that module's own module docstring, and api/services/confluence_extraction.py's
own, for why no universal host exists). This exercises the real
ORCHESTRATION logic against a plausible, hand-built simulation built
from Atlassian's own stable, published REST API documentation.
"""

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import api.services.confluence_extraction as confluence_extraction
from api.config import settings
from api.database import Base
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.documents import import_and_process_confluence_page, process_confluence_space

_BASE_URL = "https://example-tenant.atlassian.net/wiki"


def _patch_confluence_client(monkeypatch, handler):
    monkeypatch.setattr(confluence_extraction, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(settings, "CONFLUENCE_API_TOKEN", "fake-confluence-token")
    monkeypatch.setattr(settings, "CONFLUENCE_BASE_URL", _BASE_URL)


@pytest.fixture
def _stub_s3(monkeypatch):
    monkeypatch.setattr("api.security.documents.upload_document_file", lambda org_id, doc_id, filename, content, content_type: f"documents/{org_id}/{doc_id}/{filename}")


async def _make_org(session):
    owner = User(email=f"confluence-itest-{uuid.uuid4().hex[:8]}@example.com", hashed_password="irrelevant")
    session.add(owner)
    await session.flush()
    organization = Organization(name="Confluence ITest Org", slug=f"confluence-itest-{uuid.uuid4().hex[:8]}")
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=owner.id, role=OrganizationRole.owner))
    await session.commit()
    return owner, organization


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_import_and_process_confluence_page_converts_storage_html_to_a_document(monkeypatch, db_session, _stub_s3):
    """Validation criterion / vision critique Q1: la page est convertie
    et traitée via le pipeline HTML existant."""
    def handler(request):
        return httpx.Response(200, json={
            "id": "1", "title": "My Page", "space": {"key": "DOCS"},
            "version": {"number": 1, "when": "2026-01-01T00:00:00Z", "by": {"displayName": "Alice"}},
            "_links": {"webui": "/spaces/DOCS/pages/1"},
            "body": {"storage": {"value": "<p>Real page content.</p>"}},
        })

    _patch_confluence_client(monkeypatch, handler)
    owner, organization = await _make_org(db_session)

    document = await import_and_process_confluence_page(db_session, organization.id, None, owner.id, "1")

    assert document.name == "My Page"
    assert document.source_url == f"{_BASE_URL}/spaces/DOCS/pages/1"
    assert document.file_type == "text/html"


async def test_import_and_process_confluence_page_marks_failed_for_a_documented_404(monkeypatch, db_session, _stub_s3):
    def handler(request):
        return httpx.Response(404, json={"statusCode": 404, "message": "No content found"})

    _patch_confluence_client(monkeypatch, handler)
    owner, organization = await _make_org(db_session)

    with pytest.raises(ValueError, match="was not found"):
        await import_and_process_confluence_page(db_session, organization.id, None, owner.id, "nonexistent")


async def test_import_and_process_confluence_page_raises_when_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "CONFLUENCE_API_TOKEN", None)
    monkeypatch.setattr(settings, "CONFLUENCE_BASE_URL", None)
    owner, organization = await _make_org(db_session)
    with pytest.raises(ValueError, match="CONFLUENCE_API_TOKEN"):
        await import_and_process_confluence_page(db_session, organization.id, None, owner.id, "1")


async def test_process_confluence_space_fetches_and_schedules_real_pages(monkeypatch):
    """Validation criterion: l'import d'un espace fonctionne."""
    from unittest.mock import patch

    def handler(request):
        return httpx.Response(200, json={"results": [{"id": "p1"}, {"id": "p2"}]})

    _patch_confluence_client(monkeypatch, handler)
    captured = {}

    def _capture(organization_id, workspace_id, page_ids, created_by):
        captured["page_ids"] = page_ids
        return len(page_ids)

    with patch("api.security.documents.process_confluence_pages", side_effect=_capture):
        result = await process_confluence_space(uuid.uuid4(), None, "DOCS", 100, uuid.uuid4())

    assert result == "completed"
    assert captured["page_ids"] == ["p1", "p2"]


async def test_process_confluence_space_respects_the_real_include_spaces_allowlist(monkeypatch):
    """Vision critique Q2/Q3 -- a real, admin-configured guard rail on
    which spaces this server may import."""
    monkeypatch.setattr(settings, "CONFLUENCE_API_TOKEN", "fake-token")
    monkeypatch.setattr(settings, "CONFLUENCE_BASE_URL", _BASE_URL)
    monkeypatch.setattr(settings, "CONFLUENCE_INCLUDE_SPACES", "OTHER")

    result = await process_confluence_space(uuid.uuid4(), None, "DOCS", 100, uuid.uuid4())
    assert result == "failed"


async def test_process_confluence_space_returns_failed_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "CONFLUENCE_API_TOKEN", None)
    result = await process_confluence_space(uuid.uuid4(), None, "DOCS", 100, uuid.uuid4())
    assert result == "failed"
