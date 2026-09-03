"""
Partie 2.1.16 -- orchestration tests for api/security/documents.py's own
import_and_process_notion_page/process_notion_database.

Same honest limitation and testing shape as
tests/test_google_drive_integration.py's own module docstring: no real
Notion integration token is available to this automated session, so
this exercises the real ORCHESTRATION logic (fetch page, fetch the
real recursive block tree, convert to real Markdown, upload, process)
against a realistic, hand-built simulation of Notion's own
confirmed-live response shapes (`httpx.MockTransport`), not real
network.
"""

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import api.services.notion_extraction as notion_extraction
from api.config import settings
from api.database import Base
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.documents import import_and_process_notion_page, process_notion_database


def _patch_notion_client(monkeypatch, handler):
    monkeypatch.setattr(notion_extraction, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(settings, "NOTION_API_TOKEN", "fake-notion-token")


@pytest.fixture
def _stub_s3(monkeypatch):
    monkeypatch.setattr("api.security.documents.upload_document_file", lambda org_id, doc_id, filename, content, content_type: f"documents/{org_id}/{doc_id}/{filename}")


async def _make_org(session):
    owner = User(email=f"notion-itest-{uuid.uuid4().hex[:8]}@example.com", hashed_password="irrelevant")
    session.add(owner)
    await session.flush()
    organization = Organization(name="Notion ITest Org", slug=f"notion-itest-{uuid.uuid4().hex[:8]}")
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


async def test_import_and_process_notion_page_converts_a_real_shaped_page_to_markdown(monkeypatch, db_session, _stub_s3):
    """Validation criterion / vision critique Q1: la page est importée
    comme un document Markdown, via le pipeline partagé."""
    def handler(request):
        if request.url.path == "/v1/pages/page-1":
            return httpx.Response(200, json={
                "id": "page-1", "url": "https://notion.so/page-1",
                "properties": {"title": {"type": "title", "title": [{"plain_text": "My Notion Page"}]}},
            })
        if request.url.path == "/v1/blocks/page-1/children":
            return httpx.Response(200, json={"results": [
                {"id": "b1", "type": "paragraph", "has_children": False, "paragraph": {"rich_text": [{"plain_text": "Real content.", "annotations": {}}]}},
            ], "has_more": False})
        raise AssertionError(f"unexpected real request to {request.url.path}")

    _patch_notion_client(monkeypatch, handler)
    owner, organization = await _make_org(db_session)

    document = await import_and_process_notion_page(db_session, organization.id, None, owner.id, "page-1")

    assert document.name == "My Notion Page"
    assert document.source_url == "https://notion.so/page-1"
    assert document.file_type == "text/markdown"


async def test_import_and_process_notion_page_marks_failed_for_a_real_not_found_page(monkeypatch, db_session, _stub_s3):
    def handler(request):
        return httpx.Response(404, json={"object": "error", "status": 404, "code": "object_not_found", "message": "Could not find page."})

    _patch_notion_client(monkeypatch, handler)
    owner, organization = await _make_org(db_session)

    with pytest.raises(ValueError, match="not shared"):
        await import_and_process_notion_page(db_session, organization.id, None, owner.id, "nonexistent-page")


async def test_import_and_process_notion_page_raises_when_no_token_is_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "NOTION_API_TOKEN", None)
    owner, organization = await _make_org(db_session)
    with pytest.raises(ValueError, match="NOTION_API_TOKEN"):
        await import_and_process_notion_page(db_session, organization.id, None, owner.id, "page-1")


async def test_process_notion_database_queries_and_schedules_real_pages(monkeypatch):
    """Validation criterion: l'import d'une base de données fonctionne
    -- process_notion_pages (the next real layer) is monkeypatched to
    simply CAPTURE what it is called with, the same established
    boundary as every other orchestration test in this codebase."""
    from unittest.mock import patch

    def handler(request):
        return httpx.Response(200, json={"results": [{"id": "p1"}, {"id": "p2"}], "has_more": False})

    _patch_notion_client(monkeypatch, handler)

    captured = {}

    def _capture(organization_id, workspace_id, page_ids, created_by):
        captured["page_ids"] = page_ids
        return len(page_ids)

    with patch("api.security.documents.process_notion_pages", side_effect=_capture):
        result = await process_notion_database(uuid.uuid4(), None, "db-1", 100, uuid.uuid4())

    assert result == "completed"
    assert captured["page_ids"] == ["p1", "p2"]


async def test_process_notion_database_returns_failed_when_no_token_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "NOTION_API_TOKEN", None)
    result = await process_notion_database(uuid.uuid4(), None, "db-1", 100, uuid.uuid4())
    assert result == "failed"
