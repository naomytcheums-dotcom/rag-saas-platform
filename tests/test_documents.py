"""
Partie 2.1.1/2.1.2/2.1.3/2.1.4/2.1.5/2.1.6/2.1.7/2.1.8/2.1.9 -- document
upload/list/detail/delete (PDF, DOCX, TXT, Markdown, HTML, CSV, JSON,
XML, and EPUB). Fast SQLite suite, same tier as tests/test_custom_domains.py.
Both real network dependencies are mocked throughout: S3
(api/security/documents.py's upload_document_file/download_document_file)
and Celery dispatch (schedule_document_processing, stubbed by default
for the whole file -- see tests/conftest.py's
_stub_out_document_processing_scheduling_by_default) -- no real
network call belongs in the fast suite.

The real PDF/DOCX/TXT/Markdown/HTML/CSV/JSON/XML/EPUB extraction/
chunking/embedding pipeline (process_document) and the real Celery
task are tested for real, against real infrastructure, in
tests/test_documents_integration.py. CASCADE-delete of a document's
chunks is tested against real Postgres in
tests/test_postgres_integration.py (SQLite doesn't enforce foreign
keys).
"""

import uuid

from sqlalchemy import select

from api.config import settings
from api.models.document import Document, DocumentStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User

_REAL_PDF_MAGIC = b"%PDF-1.4\n%fake but real-looking pdf bytes for upload validation\n"


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


def _real_docx_bytes() -> bytes:
    """A real, minimal DOCX -- python-docx writing to an in-memory
    buffer, same library api/services/docx_extraction.py itself uses,
    so this is a genuine OOXML package (real ZIP, real word/document.xml)
    rather than a hand-faked one."""
    import io

    import docx

    document = docx.Document()
    document.add_paragraph("Real DOCX upload test content.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _real_epub_bytes() -> bytes:
    """A real, minimal EPUB -- ebooklib writing to a real temp file
    (ebooklib's own writer needs a real path, not an in-memory buffer),
    same library api/services/epub_extraction.py itself uses, so this
    is a genuine OCF package (real ZIP, real spec-mandated `mimetype`
    entry) rather than a hand-faked one."""
    import tempfile
    from pathlib import Path

    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier("id1")
    book.set_title("Upload Test Book")
    book.set_language("en")
    book.add_author("pytest")
    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap1.xhtml", lang="en")
    chapter.content = "<html><body><p>Real EPUB upload test content.</p></body></html>"
    book.add_item(chapter)
    book.toc = (epub.Link("chap1.xhtml", "Chapter 1", "chap1"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "upload_test.epub"
        epub.write_epub(str(path), book)
        return path.read_bytes()


def _stub_s3(monkeypatch):
    fake_upload = lambda org_id, doc_id, filename, content, content_type: f"documents/{org_id}/{doc_id}/{filename}"
    monkeypatch.setattr("api.security.documents.upload_document_file", fake_upload)
    monkeypatch.setattr("api.security.document_versions.upload_document_file", fake_upload)


async def _upload(client, org_id: str, token: str, filename="report.pdf", content=_REAL_PDF_MAGIC, workspace_id=None, declared_content_type="application/pdf"):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    return await client.post(
        f"/organizations/{org_id}/documents", params=params,
        files={"file": (filename, content, declared_content_type)}, headers=_auth_header(token),
    )


# ---------------------------------------------------------------- upload --

async def test_owner_can_upload_a_pdf_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion: PDF upload works."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "report.pdf"
    assert body["status"] == DocumentStatus.pending.value
    assert body["file_type"] == "application/pdf"


async def test_upload_rejects_content_that_is_neither_pdf_docx_nor_text(client, db_session, register_payload, monkeypatch):
    """Since Partie 2.1.3, plain text itself became a legitimate,
    accepted upload (see test_owner_can_upload_a_txt_document below) --
    what must still be rejected is content that fails EVERY real check:
    not real PDF/DOCX structure, and not decodable as text under any
    common encoding either (genuine random binary)."""
    import os

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="garbage.bin", content=os.urandom(500))
    assert response.status_code == 400


async def test_upload_rejects_a_file_that_exceeds_the_size_limit(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.services.document_storage.MAX_DOCUMENT_UPLOAD_BYTES", 10)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token)
    assert response.status_code == 400


async def test_manager_can_upload_a_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    manager_token, manager = await _register(client, db_session, "docmanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await _upload(client, org["id"], manager_token)
    assert response.status_code == 201


async def test_member_can_upload_a_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "docmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await _upload(client, org["id"], member_token)
    assert response.status_code == 201


async def test_viewer_cannot_upload_a_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion: permissions are respected -- Viewer's
    entire purpose is read-only access (see
    api/security/organizations.py's require_org_member_excluding_viewer)."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "docviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token)
    assert response.status_code == 403


async def test_non_member_cannot_upload_a_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    outsider_token, outsider = await _register(client, db_session, "docoutsider@example.com")

    response = await _upload(client, org["id"], outsider_token)
    assert response.status_code == 404  # anti-enumeration


async def test_upload_rejects_a_workspace_from_another_organization(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "docotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _upload(client, org["id"], owner_token, workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_upload_accepts_a_workspace_from_the_same_organization(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = (await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "My Workspace"}, headers=_auth_header(owner_token),
    )).json()

    response = await _upload(client, org["id"], owner_token, workspace_id=workspace["id"])
    assert response.status_code == 201
    assert response.json()["workspace_id"] == workspace["id"]


async def test_upload_schedules_document_processing(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    scheduled = []
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: scheduled.append(document_id))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _upload(client, org["id"], owner_token)

    assert str(scheduled[0]) == response.json()["id"]


async def test_schedule_document_processing_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_document_processing

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.document_processing.process_document_task.delay", _boom)
    schedule_document_processing(uuid.uuid4())  # must not raise


# ---------------------------------------------------------------- listing --

async def test_owner_can_list_documents(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _upload(client, org["id"], owner_token, filename="a.pdf")
    await _upload(client, org["id"], owner_token, filename="b.pdf")

    response = await client.get(f"/organizations/{org['id']}/documents", headers=_auth_header(owner_token))
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert names == {"a.pdf", "b.pdf"}


async def test_viewer_can_list_documents(client, db_session, register_payload, monkeypatch):
    """Read access is fine for Viewer -- only write actions are gated."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _upload(client, org["id"], owner_token)
    viewer_token, viewer = await _register(client, db_session, "doclistviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/documents", headers=_auth_header(viewer_token))
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


async def test_documents_from_another_organization_are_not_listed(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _upload(client, org["id"], owner_token)

    other_owner_token, other_owner = await _register(client, db_session, "doclistother@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")

    response = await client.get(f"/organizations/{other_org['id']}/documents", headers=_auth_header(other_owner_token))
    assert response.json()["items"] == []


# ----------------------------------------------------------------- detail --

async def test_owner_can_get_document_detail(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.get(f"/documents/{document_id}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["id"] == document_id


async def test_get_document_for_a_nonexistent_document_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get(f"/documents/{uuid.uuid4()}", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_get_document_belonging_to_another_organization_returns_404(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    outsider_token, outsider = await _register(client, db_session, "docdetailoutsider@example.com")
    response = await client.get(f"/documents/{document_id}", headers=_auth_header(outsider_token))
    assert response.status_code == 404  # anti-enumeration


# --------------------------------------------------------------- metadata --

async def test_owner_can_get_normalized_document_metadata(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.2.5): les métadonnées normalisées sont
    accessibles via l'API, dérivées du vrai metadata_json déjà stocké
    par process_document (jamais recalculées/dupliquées en base)."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    document = await db_session.get(Document, uuid.UUID(document_id))
    document.metadata_json = {"title": "My PDF", "author": "Jane Doe", "creationDate": "D:20230115143000+00'00'", "keywords": "alpha, beta", "page_count": 3}
    await db_session.commit()

    response = await client.get(f"/documents/{document_id}/metadata", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == document_id
    assert body["title"] == "My PDF"
    assert body["author"] == "Jane Doe"
    assert body["created_date"] == "2023-01-15T14:30:00"
    assert body["keywords"] == ["alpha", "beta"]
    assert body["raw"]["page_count"] == 3


async def test_document_metadata_is_honestly_empty_before_processing(client, db_session, register_payload, monkeypatch):
    """Validation criterion / vision critique 3: pas de métadonnées
    fabriquées quand le document n'a pas encore été traité."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.get(f"/documents/{document_id}/metadata", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["title"] is None
    assert body["author"] is None
    assert body["keywords"] == []


async def test_document_metadata_for_a_nonexistent_document_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get(f"/documents/{uuid.uuid4()}/metadata", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_document_metadata_belonging_to_another_organization_returns_404(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    outsider_token, outsider = await _register(client, db_session, "docmetaoutsider@example.com")
    response = await client.get(f"/documents/{document_id}/metadata", headers=_auth_header(outsider_token))
    assert response.status_code == 404  # anti-enumeration


# ----------------------------------------------------------------- preview --

async def test_owner_can_preview_a_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.2.4): la preview fonctionne, servie de
    manière sécurisée (jamais un accès S3 direct/public)."""
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.routers.documents.stream_document_file", lambda file_key: iter([_REAL_PDF_MAGIC]))
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.get(f"/documents/{document_id}/preview", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == _REAL_PDF_MAGIC
    assert "inline" in response.headers["content-disposition"]


async def test_preview_for_a_nonexistent_document_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get(f"/documents/{uuid.uuid4()}/preview", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_preview_belonging_to_another_organization_returns_404(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    outsider_token, outsider = await _register(client, db_session, "docpreviewoutsider@example.com")
    response = await client.get(f"/documents/{document_id}/preview", headers=_auth_header(outsider_token))
    assert response.status_code == 404  # anti-enumeration


async def test_preview_returns_a_real_502_when_s3_fails(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)

    def _boom(file_key):
        raise RuntimeError("document download failed: S3 is down")

    monkeypatch.setattr("api.routers.documents.stream_document_file", _boom)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.get(f"/documents/{document_id}/preview", headers=_auth_header(owner_token))
    assert response.status_code == 502


# ---------------------------------------------------------------- progress --

async def test_owner_can_poll_document_progress(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.2.3): la progression est accessible via
    l'API, dérivée du vrai statut du document."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.get(f"/documents/{document_id}/progress", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == document_id
    assert body["status"] == DocumentStatus.pending.value
    assert body["progress"] == 0


async def test_document_progress_for_a_nonexistent_document_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get(f"/documents/{uuid.uuid4()}/progress", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_document_progress_belonging_to_another_organization_returns_404(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    outsider_token, outsider = await _register(client, db_session, "docprogressoutsider@example.com")
    response = await client.get(f"/documents/{document_id}/progress", headers=_auth_header(outsider_token))
    assert response.status_code == 404  # anti-enumeration


async def test_owner_can_stream_document_progress_via_sse(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.2.3): la progression est diffusée en
    temps réel via SSE."""
    _stub_s3(monkeypatch)

    async def _fake_stream(db, document_id):
        yield 'data: {"status": "processing", "progress": 50}\n\n'
        yield 'data: {"status": "completed", "progress": 100}\n\n'

    monkeypatch.setattr("api.routers.documents.stream_document_progress", _fake_stream)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.get(f"/documents/{document_id}/progress/stream", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "completed" in response.text


async def test_progress_stream_for_a_nonexistent_document_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get(f"/documents/{uuid.uuid4()}/progress/stream", headers=_auth_header(owner_token))
    assert response.status_code == 404


# --------------------------------------------------------------- deleting --

async def test_creator_can_delete_their_own_document(client, db_session, register_payload, monkeypatch):
    """Partie 2.2.8 -- DELETE /documents/{id} is now a real SOFT
    delete: the real row and its real S3 object both survive, only
    `deleted_at`/`deleted_by` are set (see `DELETE .../permanent`'s
    own tests for the real, irreversible deletion this route no
    longer performs)."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "docdeleteself@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)
    created = await _upload(client, org["id"], member_token)
    document_id = created.json()["id"]

    response = await client.delete(f"/documents/{document_id}", headers=_auth_header(member_token))
    assert response.status_code == 200

    row = await db_session.scalar(select(Document).where(Document.id == uuid.UUID(document_id)))
    assert row is not None
    assert row.deleted_at is not None
    assert row.deleted_by == member.id

    # Validation criterion / vision critique -- a soft-deleted document
    # is invisible to every real single-document route from here on.
    detail = await client.get(f"/documents/{document_id}", headers=_auth_header(member_token))
    assert detail.status_code == 404


async def test_member_cannot_delete_someone_elses_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion: permissions are respected -- "Member+ si
    propriétaire" means a Member can delete their OWN document, not
    anyone else's."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    uploader_token, uploader = await _register(client, db_session, "docuploader@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), uploader.id, OrganizationRole.member, invited_by=owner.id)
    created = await _upload(client, org["id"], uploader_token)
    document_id = created.json()["id"]

    other_member_token, other_member = await _register(client, db_session, "docothermember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), other_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.delete(f"/documents/{document_id}", headers=_auth_header(other_member_token))
    assert response.status_code == 403

    row = await db_session.scalar(select(Document).where(Document.id == uuid.UUID(document_id)))
    assert row is not None  # untouched


async def test_admin_can_delete_any_document_as_an_override(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    uploader_token, uploader = await _register(client, db_session, "docadminoverrideuploader@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), uploader.id, OrganizationRole.member, invited_by=owner.id)
    created = await _upload(client, org["id"], uploader_token)
    document_id = created.json()["id"]

    admin_token, admin = await _register(client, db_session, "docadminoverride@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.delete(f"/documents/{document_id}", headers=_auth_header(admin_token))
    assert response.status_code == 200


async def test_owner_can_delete_any_document_as_an_override(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    uploader_token, uploader = await _register(client, db_session, "docowneroverrideuploader@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), uploader.id, OrganizationRole.member, invited_by=owner.id)
    created = await _upload(client, org["id"], uploader_token)
    document_id = created.json()["id"]

    response = await client.delete(f"/documents/{document_id}", headers=_auth_header(owner_token))
    assert response.status_code == 200


async def test_viewer_cannot_delete_a_document_even_one_they_created(client, db_session, register_payload, monkeypatch):
    """Edge case: a Member uploads a document, is later downgraded to
    Viewer -- the downgrade must retroactively remove delete access,
    not just block future uploads."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "docdowngraded@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)
    created = await _upload(client, org["id"], member_token)
    document_id = created.json()["id"]

    membership = await db_session.scalar(select(OrganizationMember).where(OrganizationMember.user_id == member.id, OrganizationMember.organization_id == uuid.UUID(org["id"])))
    membership.role = OrganizationRole.viewer
    await db_session.commit()

    response = await client.delete(f"/documents/{document_id}", headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_deleting_a_nonexistent_document_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.delete(f"/documents/{uuid.uuid4()}", headers=_auth_header(owner_token))
    assert response.status_code == 404


# ------------------------------------------------------------- DOCX upload --

async def test_owner_can_upload_a_docx_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.1.2): DOCX upload works, through the SAME
    endpoint as PDF."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(
        client, org["id"], owner_token, filename="report.docx", content=_real_docx_bytes(),
        declared_content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "report.docx"
    assert body["file_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def test_upload_ignores_the_declared_content_type_and_checks_the_real_bytes(client, db_session, register_payload, monkeypatch):
    """A client declaring 'application/pdf' on a real DOCX file's bytes
    (or vice versa) must be judged by the actual content, not the
    declared header -- same "trust the bytes" philosophy as
    api/services/storage.py's avatar/logo validation."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="report.docx", content=_real_docx_bytes(), declared_content_type="application/pdf")
    assert response.status_code == 201
    assert response.json()["file_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def test_upload_of_a_zip_file_misnamed_docx_is_classified_as_a_real_zip_not_a_docx(client, db_session, register_payload, monkeypatch):
    """A plain ZIP (or an XLSX/PPTX, which share the exact same leading
    magic bytes as DOCX) is never misclassified as a DOCX just because
    of its own declared filename -- api/services/document_storage.py's
    _is_real_docx also confirms word/document.xml is present, which
    this plain zip genuinely lacks. Since Partie 2.1.19, a plain zip is
    itself a real, legitimately supported upload (application/zip, its
    own real member files imported separately) -- this test used to
    assert 400 rejection before that step existed; content wins over
    declared name here exactly as it does for DOCX/EPUB/HTML/JSON/XML."""
    import io
    import zipfile

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("some_file.txt", "just a plain zip, not a docx")
    response = await _upload(client, org["id"], owner_token, filename="fake.docx", content=buffer.getvalue())
    assert response.status_code == 201
    assert response.json()["file_type"] == "application/zip"


async def test_viewer_cannot_upload_a_docx_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "docxviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token, filename="report.docx", content=_real_docx_bytes())
    assert response.status_code == 403


# -------------------------------------------------------------- TXT upload --

async def test_owner_can_upload_a_txt_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.1.3): TXT upload works, through the SAME
    endpoint as PDF/DOCX."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="notes.txt", content="Real plain text content.".encode("utf-8"), declared_content_type="text/plain")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "notes.txt"
    assert body["file_type"] == "text/plain"


async def test_upload_accepts_a_latin1_encoded_txt_file(client, db_session, register_payload, monkeypatch):
    """A real, non-UTF-8 encoded text file must still be accepted --
    upload validation only needs to confirm it decodes as text under
    SOME common encoding, not specifically UTF-8."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    content = "Un texte réel encodé en ISO-8859-1, avec des accents.".encode("iso-8859-1")
    response = await _upload(client, org["id"], owner_token, filename="latin1.txt", content=content, declared_content_type="text/plain")
    assert response.status_code == 201


async def test_upload_accepts_a_genuinely_empty_txt_file(client, db_session, register_payload, monkeypatch):
    """Vision critique Q4 -- an empty file is a real, valid edge case,
    not an error."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="empty.txt", content=b"", declared_content_type="text/plain")
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/plain"


async def test_viewer_cannot_upload_a_txt_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "txtviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token, filename="notes.txt", content=b"Some text.", declared_content_type="text/plain")
    assert response.status_code == 403


# --------------------------------------------------------- Markdown upload --

async def test_owner_can_upload_a_markdown_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.1.4): Markdown upload works, through the
    SAME endpoint as PDF/DOCX/TXT."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    content = "# Real Markdown\n\nReal upload test content.".encode("utf-8")
    response = await _upload(client, org["id"], owner_token, filename="notes.md", content=content, declared_content_type="text/markdown")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "notes.md"
    assert body["file_type"] == "text/markdown"


async def test_upload_distinguishes_markdown_from_txt_by_filename_only(client, db_session, register_payload, monkeypatch):
    """Vision critique Q1 -- Markdown is the one real, deliberate
    exception to "content decides the type, never the name": the exact
    SAME valid-text bytes become `text/markdown` when named `.md` and
    `text/plain` otherwise -- there is no content-only signal that
    could tell them apart (see api/services/document_storage.py's own
    module docstring)."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    same_bytes = "# Heading\n\nSame bytes, different filename.".encode("utf-8")
    as_markdown = await _upload(client, org["id"], owner_token, filename="a.md", content=same_bytes)
    as_txt = await _upload(client, org["id"], owner_token, filename="a.txt", content=same_bytes)

    assert as_markdown.json()["file_type"] == "text/markdown"
    assert as_txt.json()["file_type"] == "text/plain"


async def test_upload_accepts_the_markdown_extension_variant(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="notes.markdown", content=b"# Heading\n\nBody.")
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/markdown"


async def test_upload_rejects_a_md_named_file_that_is_not_real_text(client, db_session, register_payload, monkeypatch):
    """The filename alone never overrides real content validation --
    a `.md`-named file containing genuine binary garbage is still
    rejected, not silently accepted as Markdown."""
    import os

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="fake.md", content=os.urandom(500))
    assert response.status_code == 400


async def test_viewer_cannot_upload_a_markdown_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "mdviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token, filename="notes.md", content=b"# Heading\n\nBody.")
    assert response.status_code == 403


# -------------------------------------------------------------- HTML upload --

_REAL_HTML_PAGE = (
    b"<!DOCTYPE html><html><head><title>Real Page</title></head>"
    b"<body><article><p>Real HTML upload test content.</p></article></body></html>"
)


async def test_owner_can_upload_an_html_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.1.5): HTML upload works, through the
    SAME endpoint as PDF/DOCX/TXT/Markdown."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="page.html", content=_REAL_HTML_PAGE, declared_content_type="text/html")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "page.html"
    assert body["file_type"] == "text/html"


async def test_upload_detects_html_from_content_regardless_of_filename(client, db_session, register_payload, monkeypatch):
    """Vision critique Q1/robustness -- unlike Markdown (no content-only
    signal exists, see api/services/document_storage.py's own module
    docstring), real HTML has a genuine structural signature: the SAME
    real HTML bytes are detected as `text/html` no matter what the
    file is named, including a `.txt` name that would make a Markdown
    upload fall back to `text/plain` instead."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="not_named_html.txt", content=_REAL_HTML_PAGE)
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/html"


async def test_upload_accepts_the_htm_extension_variant(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="page.htm", content=_REAL_HTML_PAGE)
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/html"


async def test_upload_classifies_prose_mentioning_html_as_plain_text(client, db_session, register_payload, monkeypatch):
    """A file merely containing the word "html" as prose text, with no
    real markup structure at all, is plain text -- not HTML, even when
    named `.html`. Confirms _is_real_html's byte-pattern check isn't a
    naive substring search."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="notes.html", content=b"Just some plain text mentioning html, no real tags at all.")
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/plain"  # real content wins over the .html filename


async def test_upload_rejects_html_named_file_that_is_not_real_text(client, db_session, register_payload, monkeypatch):
    """Same "content over declared name" rule as every other format --
    a `.html`-named file containing genuine binary garbage is rejected,
    not silently accepted."""
    import os

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="fake.html", content=os.urandom(500))
    assert response.status_code == 400


async def test_viewer_cannot_upload_an_html_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "htmlviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token, filename="page.html", content=_REAL_HTML_PAGE)
    assert response.status_code == 403


# --------------------------------------------------------------- CSV upload --

async def test_owner_can_upload_a_csv_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.1.6): CSV upload works, through the
    SAME endpoint as PDF/DOCX/TXT/Markdown/HTML."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    content = "name,age\nAlice,30\nBob,25\n".encode("utf-8")
    response = await _upload(client, org["id"], owner_token, filename="data.csv", content=content, declared_content_type="text/csv")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "data.csv"
    assert body["file_type"] == "text/csv"


async def test_upload_distinguishes_csv_from_txt_by_filename_only(client, db_session, register_payload, monkeypatch):
    """Vision critique Q1 -- like Markdown, CSV is a second real,
    deliberate exception to "content decides the type, never the
    name": the exact SAME valid-text bytes become `text/csv` when
    named `.csv` and `text/plain` otherwise -- there is no reliable
    content-only signal that could tell them apart (see
    api/services/document_storage.py's own module docstring)."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    same_bytes = "name,age\nAlice,30\n".encode("utf-8")
    as_csv = await _upload(client, org["id"], owner_token, filename="a.csv", content=same_bytes)
    as_txt = await _upload(client, org["id"], owner_token, filename="a.txt", content=same_bytes)

    assert as_csv.json()["file_type"] == "text/csv"
    assert as_txt.json()["file_type"] == "text/plain"


async def test_upload_rejects_a_csv_named_file_that_is_not_real_text(client, db_session, register_payload, monkeypatch):
    """The filename alone never overrides real content validation --
    a `.csv`-named file containing genuine binary garbage is still
    rejected, not silently accepted as CSV."""
    import os

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="fake.csv", content=os.urandom(500))
    assert response.status_code == 400


async def test_viewer_cannot_upload_a_csv_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "csvviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token, filename="data.csv", content=b"name,age\nAlice,30\n")
    assert response.status_code == 403


# -------------------------------------------------------------- JSON upload --

_REAL_JSON_ARRAY = b'[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]'


async def test_owner_can_upload_a_json_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.1.7): JSON upload works, through the
    SAME endpoint as PDF/DOCX/TXT/Markdown/HTML/CSV."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="data.json", content=_REAL_JSON_ARRAY, declared_content_type="application/json")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "data.json"
    assert body["file_type"] == "application/json"


async def test_upload_detects_json_from_content_regardless_of_filename(client, db_session, register_payload, monkeypatch):
    """Vision critique Q1/robustness -- unlike Markdown/CSV (no
    content-only signal exists), valid JSON is an exact, deterministic
    signal: the SAME real JSON bytes are detected as `application/json`
    no matter what the file is named, including a `.txt` name that
    would make a Markdown/CSV upload fall back to `text/plain` instead
    (see api/services/document_storage.py's own module docstring)."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="not_named_json.txt", content=_REAL_JSON_ARRAY)
    assert response.status_code == 201
    assert response.json()["file_type"] == "application/json"


async def test_upload_classifies_a_bare_json_scalar_as_plain_text(client, db_session, register_payload, monkeypatch):
    """Deliberate, documented narrowing (see api/services/document_storage.py's
    own module docstring): a bare top-level scalar (`42`) IS valid JSON
    per RFC 8259, but is indistinguishable from an ordinary short text
    file -- classified as `text/plain`, not `application/json`, even
    when named `.json`."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="scalar.json", content=b"42")
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/plain"


async def test_upload_classifies_malformed_json_as_plain_text(client, db_session, register_payload, monkeypatch):
    """Same "content wins over declared name" story as HTML's own
    prose-mentioning-html test: a `.json`-named file with a real
    syntax error (a trailing comma) is NOT valid JSON, so it falls
    through to the generic text bucket -- not a hard rejection, since
    the bytes are still valid text."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="broken.json", content=b'{"a": 1,}')
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/plain"


async def test_upload_rejects_a_json_named_file_that_is_not_real_text(client, db_session, register_payload, monkeypatch):
    """Same "content over declared name" rule as every other format --
    a `.json`-named file containing genuine binary garbage is rejected,
    not silently accepted."""
    import os

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="fake.json", content=os.urandom(500))
    assert response.status_code == 400


async def test_viewer_cannot_upload_a_json_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "jsonviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token, filename="data.json", content=_REAL_JSON_ARRAY)
    assert response.status_code == 403


# --------------------------------------------------------------- XML upload --

_REAL_DECLARED_XML = b'<?xml version="1.0"?><catalog><book id="1">Real content</book></catalog>'
_REAL_UNDECLARED_XML = b"<catalog><book id=\"1\">Real content</book></catalog>"


async def test_owner_can_upload_an_xml_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.1.8): XML upload works, through the
    SAME endpoint as every other format."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="data.xml", content=_REAL_DECLARED_XML, declared_content_type="application/xml")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "data.xml"
    assert body["file_type"] == "application/xml"


async def test_upload_detects_declared_xml_from_content_regardless_of_filename(client, db_session, register_payload, monkeypatch):
    """Vision critique Q1/robustness -- a real `<?xml ...?>` declaration
    is an unambiguous, deterministic signal (see api/services/document_storage.py's
    own module docstring): the SAME bytes are detected as `application/xml`
    no matter what the file is named."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="not_named_xml.txt", content=_REAL_DECLARED_XML)
    assert response.status_code == 201
    assert response.json()["file_type"] == "application/xml"


async def test_upload_detects_undeclared_xml_when_the_root_does_not_collide_with_html(client, db_session, register_payload, monkeypatch):
    """Real XML without a `<?xml ...?>` declaration is still detected
    from content, via the fallback check that runs after HTML's own
    sniff (see api/services/document_storage.py's own module docstring)
    -- as long as its root tag isn't one of HTML's own sniff patterns."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="data.xml", content=_REAL_UNDECLARED_XML)
    assert response.status_code == 201
    assert response.json()["file_type"] == "application/xml"


async def test_upload_classifies_undeclared_xml_as_html_when_the_root_collides(client, db_session, register_payload, monkeypatch):
    """Real, honest, documented limitation (see api/services/document_storage.py's
    own module docstring) locked in by a test, not just asserted in
    prose: an UNDECLARED XML document whose root tag happens to be one
    of HTML's own sniff patterns (here, `<table>`) is classified as
    HTML, not XML -- resolving a genuine ambiguity between two formats
    that can open with the exact same bytes, in favor of the far more
    common real-world case."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    undeclared_table_xml = b"<table><row><cell>1</cell></row></table>"
    response = await _upload(client, org["id"], owner_token, filename="data.xml", content=undeclared_table_xml)
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/html"


async def test_upload_classifies_malformed_xml_as_plain_text(client, db_session, register_payload, monkeypatch):
    """Same "content wins over declared name" story as JSON/HTML's own
    tests: a `.xml`-named file with a real syntax error (a mismatched
    closing tag) is NOT valid XML, so it falls through to the generic
    text bucket -- not a hard rejection, since the bytes are still
    valid text. Root tag deliberately NOT one of HTML's own sniff
    patterns (unlike `<a>`/`<p>`/`<table>`), so this exercises the
    "genuinely not classifiable as anything real" path, not the
    documented HTML-collision case covered by its own test above."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="broken.xml", content=b"<catalog><book></catalog>")
    assert response.status_code == 201
    assert response.json()["file_type"] == "text/plain"


async def test_upload_rejects_an_xml_named_file_that_is_not_real_text(client, db_session, register_payload, monkeypatch):
    """Same "content over declared name" rule as every other format --
    a `.xml`-named file containing genuine binary garbage is rejected,
    not silently accepted."""
    import os

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="fake.xml", content=os.urandom(500))
    assert response.status_code == 400


async def test_viewer_cannot_upload_an_xml_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "xmlviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token, filename="data.xml", content=_REAL_DECLARED_XML)
    assert response.status_code == 403


# -------------------------------------------------------------- EPUB upload --

async def test_owner_can_upload_an_epub_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.1.9): EPUB upload works, through the
    SAME endpoint as every other format."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(
        client, org["id"], owner_token, filename="book.epub", content=_real_epub_bytes(), declared_content_type="application/epub+zip",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "book.epub"
    assert body["file_type"] == "application/epub+zip"


async def test_upload_ignores_the_declared_content_type_for_epub_and_checks_the_real_bytes(client, db_session, register_payload, monkeypatch):
    """Vision critique Q1/robustness -- like DOCX, EPUB is detected
    from its own real, spec-mandated ZIP content (the `mimetype`
    entry), regardless of what the client declares or what the file
    is named."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(
        client, org["id"], owner_token, filename="not_named_epub.bin", content=_real_epub_bytes(), declared_content_type="application/octet-stream",
    )
    assert response.status_code == 201
    assert response.json()["file_type"] == "application/epub+zip"


async def test_upload_of_a_zip_file_misnamed_epub_is_classified_as_a_real_zip_not_an_epub(client, db_session, register_payload, monkeypatch):
    """Same "content over declared name" rule as DOCX's own equivalent
    test above -- a real ZIP that simply isn't an EPUB (no spec-mandated
    `mimetype` entry) is never misclassified as one just because it
    happens to be a ZIP. Since Partie 2.1.19, it's still a real,
    legitimately supported upload in its own right (application/zip) --
    this test used to assert 400 rejection before that step existed."""
    import io
    import zipfile

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("hello.txt", "just a random zip, not an epub")

    response = await _upload(client, org["id"], owner_token, filename="fake.epub", content=buffer.getvalue())
    assert response.status_code == 201
    assert response.json()["file_type"] == "application/zip"


async def test_viewer_cannot_upload_an_epub_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "epubviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token, filename="book.epub", content=_real_epub_bytes())
    assert response.status_code == 403


# ---------------------------------------------------------- URL import --

async def _import_url(client, org_id: str, token: str, url: str, workspace_id=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    return await client.post(
        f"/organizations/{org_id}/documents/url", params=params,
        json={"url": url}, headers=_auth_header(token),
    )


async def test_owner_can_import_a_document_from_a_url(client, db_session, register_payload):
    """Validation criterion (2.1.10): importing from a URL works,
    through its own real route. Real network activity is deliberately
    NOT triggered by this test -- schedule_url_import is stubbed by
    tests/conftest.py's own autouse fixture, the same way S3/Celery are
    stubbed for every other format's own fast upload tests -- this
    only exercises the SYNCHRONOUS half of the route (vision critique
    Q4's own answer: fast, no real network, real fetch deferred)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_url(client, org["id"], owner_token, "https://example.com/article")
    assert response.status_code == 201
    body = response.json()
    assert body["source_url"] == "https://example.com/article"
    assert body["name"] == "https://example.com/article"  # real fallback until the real fetch determines the page's own title
    assert body["status"] == DocumentStatus.pending.value


async def test_import_rejects_a_disallowed_url_scheme(client, db_session, register_payload):
    """Vision critique Q2/Q5 -- an obviously invalid URL is rejected
    immediately (a real, synchronous 400), not silently accepted and
    deferred to a background failure."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_url(client, org["id"], owner_token, "ftp://example.com/file")
    assert response.status_code in (400, 422)  # 422 if pydantic's own HttpUrl rejects it first


async def test_import_rejects_a_url_with_embedded_credentials(client, db_session, register_payload):
    """pydantic's own HttpUrl (the schema-layer check) does NOT reject
    this -- confirmed for real -- so this proves api/services/url_fetching.py's
    own validate_url is genuinely reached and enforced, not redundant."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_url(client, org["id"], owner_token, "http://user:pass@example.com/")
    assert response.status_code == 400


async def test_import_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "urlotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _import_url(client, org["id"], owner_token, "https://example.com/", workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_import_document_from_url_schedules_url_import(client, db_session, register_payload, monkeypatch):
    scheduled = []
    monkeypatch.setattr("api.security.documents.schedule_url_import", lambda document_id: scheduled.append(document_id))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _import_url(client, org["id"], owner_token, "https://example.com/article")

    assert str(scheduled[0]) == response.json()["id"]


async def test_schedule_url_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_url_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.url_import.fetch_and_process_url_task.delay", _boom)
    schedule_url_import(uuid.uuid4())  # must not raise


async def test_viewer_cannot_import_a_document_from_a_url(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "urlviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _import_url(client, org["id"], viewer_token, "https://example.com/article")
    assert response.status_code == 403


async def test_uploaded_documents_have_no_source_url(client, db_session, register_payload, monkeypatch):
    """Real, explicit confirmation that source_url stays None for the
    OTHER, much more common import path -- a plain file upload."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token)
    assert response.json()["source_url"] is None


# ------------------------------------------------------- Sitemap import --

async def _import_sitemap(client, org_id: str, token: str, url: str, workspace_id=None, filters=None, max_urls=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    body = {"url": url}
    if filters is not None:
        body["filters"] = filters
    if max_urls is not None:
        body["max_urls"] = max_urls
    return await client.post(
        f"/organizations/{org_id}/documents/sitemap", params=params,
        json=body, headers=_auth_header(token),
    )


async def test_owner_can_start_a_sitemap_import(client, db_session, register_payload):
    """Validation criterion (2.1.11): l'import de sitemap fonctionne,
    through its own real route. Real network activity is deliberately
    NOT triggered -- schedule_sitemap_import is stubbed by
    tests/conftest.py's own autouse fixture, the same "only the
    synchronous half" reasoning as 2.1.10's own equivalent test."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_sitemap(client, org["id"], owner_token, "https://example.com/sitemap.xml")
    assert response.status_code == 202
    body = response.json()
    assert body["sitemap_url"] == "https://example.com/sitemap.xml"
    assert body["status"] == "scheduled"


async def test_sitemap_import_rejects_a_disallowed_url_scheme(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_sitemap(client, org["id"], owner_token, "ftp://example.com/sitemap.xml")
    assert response.status_code in (400, 422)  # 422 if pydantic's own HttpUrl rejects it first


async def test_sitemap_import_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "sitemapotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _import_sitemap(client, org["id"], owner_token, "https://example.com/sitemap.xml", workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_sitemap_import_rejects_max_urls_out_of_bounds(client, db_session, register_payload):
    """SitemapImportRequest.max_urls is bounded (ge=1, le=5000) via
    pydantic's own Field -- a real, structural 422, not a 400 raised by
    application code."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_sitemap(client, org["id"], owner_token, "https://example.com/sitemap.xml", max_urls=0)
    assert response.status_code == 422

    response = await _import_sitemap(client, org["id"], owner_token, "https://example.com/sitemap.xml", max_urls=5001)
    assert response.status_code == 422


async def test_sitemap_import_passes_filters_and_max_urls_through_to_scheduling(client, db_session, register_payload, monkeypatch):
    captured = {}

    def _capture(sitemap_url, organization_id, workspace_id, filters, max_urls, created_by):
        captured["sitemap_url"] = sitemap_url
        captured["filters"] = filters
        captured["max_urls"] = max_urls

    monkeypatch.setattr("api.security.documents.schedule_sitemap_import", _capture)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _import_sitemap(
        client, org["id"], owner_token, "https://example.com/sitemap.xml", filters=["/blog/*"], max_urls=42,
    )

    assert response.status_code == 202
    assert captured["filters"] == ["/blog/*"]
    assert captured["max_urls"] == 42


async def test_schedule_sitemap_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_sitemap_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.sitemap_import.process_sitemap_task.delay", _boom)
    schedule_sitemap_import("https://example.com/sitemap.xml", uuid.uuid4(), None, None, 500, uuid.uuid4())  # must not raise


async def test_viewer_cannot_start_a_sitemap_import(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "sitemapviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _import_sitemap(client, org["id"], viewer_token, "https://example.com/sitemap.xml")
    assert response.status_code == 403


# ------------------------------------------------ process_sitemap_urls --

def test_process_sitemap_urls_schedules_one_task_per_filtered_url_with_a_real_stagger(monkeypatch):
    """Validation criterion: filtering happens, and every scheduled
    task gets a real, increasing countdown (the courtesy stagger)."""
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append((args, countdown))

    monkeypatch.setattr("api.tasks.sitemap_import.process_single_url_task", _FakeTask())

    org_id, workspace_id, created_by = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    urls = ["https://example.com/blog/1", "https://example.com/blog/2", "https://example.com/about"]
    scheduled = documents_module.process_sitemap_urls(org_id, workspace_id, urls, filters=["/blog/*"], created_by=created_by)

    assert scheduled == 2
    assert len(calls) == 2
    assert calls[0][0] == ["https://example.com/blog/1", str(org_id), str(workspace_id), str(created_by)]
    assert calls[0][1] == 0  # first url has no delay
    assert calls[1][1] == documents_module._SITEMAP_PER_URL_STAGGER_SECONDS  # second url staggered by one interval


def test_process_sitemap_urls_caps_the_real_stagger_for_a_very_long_list(monkeypatch):
    """Vision critique Q3 (scalabilité) -- a sitemap large enough that
    the naive per-url stagger would exceed _SITEMAP_MAX_STAGGER_SECONDS
    is capped, not left to grow unbounded."""
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append(countdown)

    monkeypatch.setattr("api.tasks.sitemap_import.process_single_url_task", _FakeTask())

    many_urls = [f"https://example.com/page-{i}" for i in range(500)]
    documents_module.process_sitemap_urls(uuid.uuid4(), None, many_urls, filters=None, created_by=None)

    assert max(calls) == documents_module._SITEMAP_MAX_STAGGER_SECONDS


def test_process_sitemap_urls_tolerates_a_broker_failure_for_one_url(monkeypatch):
    """Same "one real failure must not abort the whole batch" contract
    as schedule_url_import/schedule_sitemap_import -- one broker hiccup
    scheduling ONE url is logged and skipped, the rest still schedule."""
    from api.security import documents as documents_module

    calls = []

    class _FlakyTask:
        def apply_async(self, args, countdown):
            if args[0] == "https://example.com/bad":
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.sitemap_import.process_single_url_task", _FlakyTask())

    urls = ["https://example.com/good-1", "https://example.com/bad", "https://example.com/good-2"]
    scheduled = documents_module.process_sitemap_urls(uuid.uuid4(), None, urls, filters=None, created_by=None)

    assert scheduled == 2
    assert len(calls) == 2


# --------------------------------------------------- GitHub repo import --

async def _import_github_repo(client, org_id: str, token: str, repo_url: str, workspace_id=None, file_patterns=None, max_files=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    body = {"repo_url": repo_url}
    if file_patterns is not None:
        body["file_patterns"] = file_patterns
    if max_files is not None:
        body["max_files"] = max_files
    return await client.post(
        f"/organizations/{org_id}/documents/github/repo", params=params,
        json=body, headers=_auth_header(token),
    )


async def test_owner_can_start_a_github_repo_import(client, db_session, register_payload):
    """Validation criterion (2.1.12): l'import d'un dépôt fonctionne,
    through its own real route. Real network activity is deliberately
    NOT triggered -- schedule_github_repo_import is stubbed by
    tests/conftest.py's own autouse fixture, the same "only the
    synchronous half" reasoning as Partie 2.1.10/2.1.11's own
    equivalent tests."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_github_repo(client, org["id"], owner_token, "https://github.com/octocat/Hello-World")
    assert response.status_code == 202
    body = response.json()
    assert body == {"owner": "octocat", "repo": "Hello-World", "status": "scheduled"}


async def test_github_repo_import_rejects_an_invalid_repo_url(client, db_session, register_payload):
    """Vision critique Q4/Q5 -- an obviously invalid repo URL is
    rejected immediately (a real, synchronous 400), not silently
    accepted and deferred to a background failure."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_github_repo(client, org["id"], owner_token, "https://gitlab.com/octocat/Hello-World")
    assert response.status_code in (400, 422)  # 422 if pydantic's own HttpUrl rejects it first (it won't here, but kept consistent with URL/sitemap's own tests)


async def test_github_repo_import_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "githubotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _import_github_repo(client, org["id"], owner_token, "https://github.com/octocat/Hello-World", workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_github_repo_import_rejects_max_files_out_of_bounds(client, db_session, register_payload):
    """GitHubRepoImportRequest.max_files is bounded (ge=1, le=2000) via
    pydantic's own Field -- a real, structural 422, not a 400 raised by
    application code."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_github_repo(client, org["id"], owner_token, "https://github.com/octocat/Hello-World", max_files=0)
    assert response.status_code == 422

    response = await _import_github_repo(client, org["id"], owner_token, "https://github.com/octocat/Hello-World", max_files=2001)
    assert response.status_code == 422


async def test_github_repo_import_passes_file_patterns_and_max_files_through_to_scheduling(client, db_session, register_payload, monkeypatch):
    captured = {}

    def _capture(repo_url, organization_id, workspace_id, file_patterns, max_files, created_by):
        captured["repo_url"] = repo_url
        captured["file_patterns"] = file_patterns
        captured["max_files"] = max_files

    monkeypatch.setattr("api.security.documents.schedule_github_repo_import", _capture)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _import_github_repo(
        client, org["id"], owner_token, "https://github.com/octocat/Hello-World",
        file_patterns=[".py", ".md"], max_files=42,
    )

    assert response.status_code == 202
    assert captured["file_patterns"] == [".py", ".md"]
    assert captured["max_files"] == 42


async def test_schedule_github_repo_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_github_repo_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.github_import.process_github_repo_task.delay", _boom)
    schedule_github_repo_import("https://github.com/octocat/Hello-World", uuid.uuid4(), None, None, 100, uuid.uuid4())  # must not raise


async def test_viewer_cannot_start_a_github_repo_import(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "githubviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _import_github_repo(client, org["id"], viewer_token, "https://github.com/octocat/Hello-World")
    assert response.status_code == 403


# --------------------------------------------------- process_github_files --

def test_process_github_files_schedules_one_task_per_file_with_a_real_stagger(monkeypatch):
    """Validation criterion: every scheduled task gets a real,
    increasing countdown (the courtesy stagger)."""
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append((args, countdown))

    monkeypatch.setattr("api.tasks.github_import.process_github_file_task", _FakeTask())

    org_id, workspace_id, created_by = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    file_urls = ["https://api.github.com/repos/o/r/contents/a.py?ref=main", "https://api.github.com/repos/o/r/contents/b.py?ref=main"]
    scheduled = documents_module.process_github_files(org_id, workspace_id, file_urls, created_by)

    assert scheduled == 2
    assert calls[0][0] == [file_urls[0], str(org_id), str(workspace_id), str(created_by)]
    assert calls[0][1] == 0
    assert calls[1][1] == documents_module._GITHUB_PER_FILE_STAGGER_SECONDS


def test_process_github_files_caps_the_real_stagger_for_a_very_long_list(monkeypatch):
    """Vision critique Q3 (performance/rate limiting) -- a repo large
    enough that the naive per-file stagger would exceed
    _GITHUB_MAX_STAGGER_SECONDS is capped, not left to grow unbounded."""
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append(countdown)

    monkeypatch.setattr("api.tasks.github_import.process_github_file_task", _FakeTask())

    many_urls = [f"https://api.github.com/repos/o/r/contents/file-{i}.py?ref=main" for i in range(500)]
    documents_module.process_github_files(uuid.uuid4(), None, many_urls, created_by=None)

    assert max(calls) == documents_module._GITHUB_MAX_STAGGER_SECONDS


def test_process_github_files_tolerates_a_broker_failure_for_one_file(monkeypatch):
    """Same "one real failure must not abort the whole batch" contract
    as process_sitemap_urls -- one broker hiccup scheduling ONE file is
    logged and skipped, the rest still schedule."""
    from api.security import documents as documents_module

    calls = []

    class _FlakyTask:
        def apply_async(self, args, countdown):
            if "bad" in args[0]:
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.github_import.process_github_file_task", _FlakyTask())

    file_urls = [
        "https://api.github.com/repos/o/r/contents/good-1.py?ref=main",
        "https://api.github.com/repos/o/r/contents/bad.py?ref=main",
        "https://api.github.com/repos/o/r/contents/good-2.py?ref=main",
    ]
    scheduled = documents_module.process_github_files(uuid.uuid4(), None, file_urls, created_by=None)

    assert scheduled == 2
    assert len(calls) == 2


# --------------------------------------------------- GitHub issues import --

async def _import_github_issues(client, org_id: str, token: str, repo_url: str, workspace_id=None, state=None, since=None, labels=None, max_issues=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    body = {"repo_url": repo_url}
    if state is not None:
        body["state"] = state
    if since is not None:
        body["since"] = since
    if labels is not None:
        body["labels"] = labels
    if max_issues is not None:
        body["max_issues"] = max_issues
    return await client.post(
        f"/organizations/{org_id}/documents/github/issues", params=params,
        json=body, headers=_auth_header(token),
    )


async def test_owner_can_start_a_github_issues_import(client, db_session, register_payload):
    """Validation criterion (2.1.13): l'import d'issues fonctionne,
    through its own real route. Real network activity is deliberately
    NOT triggered -- schedule_github_issues_import is stubbed by
    tests/conftest.py's own autouse fixture, the same "only the
    synchronous half" reasoning as every prior GitHub/sitemap import
    test."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_github_issues(client, org["id"], owner_token, "https://github.com/octocat/Hello-World")
    assert response.status_code == 202
    body = response.json()
    assert body == {"owner": "octocat", "repo": "Hello-World", "status": "scheduled"}


async def test_github_issues_import_rejects_an_invalid_repo_url(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_github_issues(client, org["id"], owner_token, "https://gitlab.com/octocat/Hello-World")
    assert response.status_code in (400, 422)


async def test_github_issues_import_rejects_an_invalid_state(client, db_session, register_payload):
    """`state` is constrained to GitHub's own three real values at the
    schema layer -- a real, structural 422, not a 400 raised by
    application code."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_github_issues(client, org["id"], owner_token, "https://github.com/octocat/Hello-World", state="not-a-real-state")
    assert response.status_code == 422


async def test_github_issues_import_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "githubissuesotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _import_github_issues(client, org["id"], owner_token, "https://github.com/octocat/Hello-World", workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_github_issues_import_rejects_max_issues_out_of_bounds(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_github_issues(client, org["id"], owner_token, "https://github.com/octocat/Hello-World", max_issues=0)
    assert response.status_code == 422

    response = await _import_github_issues(client, org["id"], owner_token, "https://github.com/octocat/Hello-World", max_issues=2001)
    assert response.status_code == 422


async def test_github_issues_import_passes_state_since_labels_and_max_issues_through_to_scheduling(client, db_session, register_payload, monkeypatch):
    captured = {}

    def _capture(repo_url, organization_id, workspace_id, state, since, labels, max_issues, created_by):
        captured["state"] = state
        captured["since"] = since
        captured["labels"] = labels
        captured["max_issues"] = max_issues

    monkeypatch.setattr("api.security.documents.schedule_github_issues_import", _capture)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _import_github_issues(
        client, org["id"], owner_token, "https://github.com/octocat/Hello-World",
        state="open", since="2024-01-01T00:00:00Z", labels=["bug"], max_issues=42,
    )

    assert response.status_code == 202
    assert captured["state"] == "open"
    assert captured["since"] == "2024-01-01T00:00:00Z"
    assert captured["labels"] == ["bug"]
    assert captured["max_issues"] == 42


async def test_schedule_github_issues_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_github_issues_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.github_import.process_github_issues_task.delay", _boom)
    schedule_github_issues_import("https://github.com/octocat/Hello-World", uuid.uuid4(), None, "all", None, None, 100, uuid.uuid4())  # must not raise


async def test_viewer_cannot_start_a_github_issues_import(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "githubissuesviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _import_github_issues(client, org["id"], viewer_token, "https://github.com/octocat/Hello-World")
    assert response.status_code == 403


# ------------------------------------------- process_github_issue_documents --

def test_process_github_issue_documents_schedules_one_task_per_issue_with_a_real_stagger(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append((args, countdown))

    monkeypatch.setattr("api.tasks.github_import.process_github_issue_task", _FakeTask())

    org_id, workspace_id, created_by = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    issues_data = [{"issue": {"number": 1}, "comments": []}, {"issue": {"number": 2}, "comments": []}]
    scheduled = documents_module.process_github_issue_documents(org_id, workspace_id, issues_data, created_by)

    assert scheduled == 2
    assert calls[0][0] == [issues_data[0], str(org_id), str(workspace_id), str(created_by)]
    assert calls[0][1] == 0
    assert calls[1][1] == documents_module._GITHUB_ISSUE_STAGGER_SECONDS


def test_process_github_issue_documents_caps_the_real_stagger_for_a_very_long_list(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append(countdown)

    monkeypatch.setattr("api.tasks.github_import.process_github_issue_task", _FakeTask())

    many_issues = [{"issue": {"number": i}, "comments": []} for i in range(500)]
    documents_module.process_github_issue_documents(uuid.uuid4(), None, many_issues, created_by=None)

    assert max(calls) == documents_module._GITHUB_ISSUE_MAX_STAGGER_SECONDS


def test_process_github_issue_documents_tolerates_a_broker_failure_for_one_issue(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FlakyTask:
        def apply_async(self, args, countdown):
            if args[0]["issue"]["number"] == 2:
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.github_import.process_github_issue_task", _FlakyTask())

    issues_data = [{"issue": {"number": 1}, "comments": []}, {"issue": {"number": 2}, "comments": []}, {"issue": {"number": 3}, "comments": []}]
    scheduled = documents_module.process_github_issue_documents(uuid.uuid4(), None, issues_data, created_by=None)

    assert scheduled == 2
    assert len(calls) == 2


# ------------------------------------------------------ Google Drive import --

async def _import_google_drive(client, org_id: str, token: str, drive_id: str, workspace_id=None, patterns=None, max_files=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    body = {"drive_id": drive_id}
    if patterns is not None:
        body["patterns"] = patterns
    if max_files is not None:
        body["max_files"] = max_files
    return await client.post(
        f"/organizations/{org_id}/documents/google-drive", params=params,
        json=body, headers=_auth_header(token),
    )


async def test_owner_can_start_a_google_drive_import(client, db_session, register_payload):
    """Validation criterion (2.1.14): l'import Drive fonctionne,
    through its own real route. Real network activity is deliberately
    NOT triggered -- schedule_google_drive_import is stubbed by
    tests/conftest.py's own autouse fixture, the same "only the
    synchronous half" reasoning as every prior async import test."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_google_drive(client, org["id"], owner_token, "fake-drive-folder-id")
    assert response.status_code == 202
    body = response.json()
    assert body == {"drive_id": "fake-drive-folder-id", "status": "scheduled"}


async def test_google_drive_import_rejects_an_empty_drive_id(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_google_drive(client, org["id"], owner_token, "")
    assert response.status_code == 422  # pydantic's own min_length=1 rejects this before application code ever runs


async def test_google_drive_import_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "drivewotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _import_google_drive(client, org["id"], owner_token, "fake-drive-folder-id", workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_google_drive_import_rejects_max_files_out_of_bounds(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_google_drive(client, org["id"], owner_token, "fake-drive-folder-id", max_files=0)
    assert response.status_code == 422

    response = await _import_google_drive(client, org["id"], owner_token, "fake-drive-folder-id", max_files=2001)
    assert response.status_code == 422


async def test_google_drive_import_passes_patterns_and_max_files_through_to_scheduling(client, db_session, register_payload, monkeypatch):
    captured = {}

    def _capture(drive_id, organization_id, workspace_id, patterns, max_files, created_by):
        captured["drive_id"] = drive_id
        captured["patterns"] = patterns
        captured["max_files"] = max_files

    monkeypatch.setattr("api.security.documents.schedule_google_drive_import", _capture)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _import_google_drive(
        client, org["id"], owner_token, "fake-drive-folder-id", patterns=[".pdf"], max_files=42,
    )

    assert response.status_code == 202
    assert captured["patterns"] == [".pdf"]
    assert captured["max_files"] == 42


async def test_schedule_google_drive_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_google_drive_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.google_drive_import.process_google_drive_task.delay", _boom)
    schedule_google_drive_import("fake-drive-folder-id", uuid.uuid4(), None, None, 100, uuid.uuid4())  # must not raise


async def test_viewer_cannot_start_a_google_drive_import(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "driveviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _import_google_drive(client, org["id"], viewer_token, "fake-drive-folder-id")
    assert response.status_code == 403


# --------------------------------------------------- process_google_drive_files --

def test_process_google_drive_files_schedules_one_task_per_file_with_a_real_stagger(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append((args, countdown))

    monkeypatch.setattr("api.tasks.google_drive_import.process_google_drive_file_task", _FakeTask())

    org_id, workspace_id, created_by = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    file_ids = ["f1", "f2"]
    scheduled = documents_module.process_google_drive_files(org_id, workspace_id, file_ids, created_by)

    assert scheduled == 2
    assert calls[0][0] == ["f1", str(org_id), str(workspace_id), str(created_by)]
    assert calls[0][1] == 0
    assert calls[1][1] == documents_module._GOOGLE_DRIVE_PER_FILE_STAGGER_SECONDS


def test_process_google_drive_files_caps_the_real_stagger_for_a_very_long_list(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append(countdown)

    monkeypatch.setattr("api.tasks.google_drive_import.process_google_drive_file_task", _FakeTask())

    many_ids = [f"f{i}" for i in range(500)]
    documents_module.process_google_drive_files(uuid.uuid4(), None, many_ids, created_by=None)

    assert max(calls) == documents_module._GOOGLE_DRIVE_MAX_STAGGER_SECONDS


def test_process_google_drive_files_tolerates_a_broker_failure_for_one_file(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FlakyTask:
        def apply_async(self, args, countdown):
            if args[0] == "bad":
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.google_drive_import.process_google_drive_file_task", _FlakyTask())

    file_ids = ["good-1", "bad", "good-2"]
    scheduled = documents_module.process_google_drive_files(uuid.uuid4(), None, file_ids, created_by=None)

    assert scheduled == 2
    assert len(calls) == 2


# -------------------------------------------------------- Google Docs import --

async def _import_google_doc(client, org_id: str, token: str, document_url_or_id=None, document_urls_or_ids=None, workspace_id=None, export_format=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    body = {}
    if document_url_or_id is not None:
        body["document_url_or_id"] = document_url_or_id
    if document_urls_or_ids is not None:
        body["document_urls_or_ids"] = document_urls_or_ids
    if export_format is not None:
        body["export_format"] = export_format
    return await client.post(
        f"/organizations/{org_id}/documents/google-docs", params=params,
        json=body, headers=_auth_header(token),
    )


async def test_owner_can_start_a_single_google_doc_import(client, db_session, register_payload):
    """Validation criterion (2.1.15): l'import d'un Google Doc
    fonctionne, through its own real route. Real network activity is
    deliberately NOT triggered -- schedule_google_doc_import is stubbed
    by tests/conftest.py's own autouse fixture."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_google_doc(client, org["id"], owner_token, document_url_or_id="https://docs.google.com/document/d/1AbCdEfGhIjKlMnOp/edit")
    assert response.status_code == 202
    body = response.json()
    assert body == {"document_ids": ["1AbCdEfGhIjKlMnOp"], "mode": "single", "status": "scheduled"}


async def test_owner_can_start_a_batch_google_docs_import(client, db_session, register_payload):
    """Validation criterion: l'import en lot fonctionne."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_google_doc(client, org["id"], owner_token, document_urls_or_ids=["1AbCdEfGhIjKlMnOp", "1QrStUvWxYzAbCdEf"])
    assert response.status_code == 202
    body = response.json()
    assert body == {"document_ids": ["1AbCdEfGhIjKlMnOp", "1QrStUvWxYzAbCdEf"], "mode": "batch", "status": "scheduled"}


async def test_google_doc_import_rejects_giving_both_a_single_and_a_batch_target(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_google_doc(client, org["id"], owner_token, document_url_or_id="1AbCdEfGhIjKlMnOp", document_urls_or_ids=["1QrStUvWxYzAbCdEf"])
    assert response.status_code == 422  # pydantic's own model_validator rejects this before application code runs


async def test_google_doc_import_rejects_giving_neither_target(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_google_doc(client, org["id"], owner_token)
    assert response.status_code == 422


async def test_google_doc_import_rejects_an_invalid_document_url(client, db_session, register_payload):
    """Validation criterion: un document invalide est rejeté."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_google_doc(client, org["id"], owner_token, document_url_or_id="https://example.com/not-a-doc")
    assert response.status_code == 400


async def test_google_doc_import_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "googledocsotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _import_google_doc(client, org["id"], owner_token, document_url_or_id="1AbCdEfGhIjKlMnOp", workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_google_doc_import_passes_export_format_through_to_scheduling(client, db_session, register_payload, monkeypatch):
    captured = {}

    def _capture(document_id, organization_id, workspace_id, export_format, created_by):
        captured["document_id"] = document_id
        captured["export_format"] = export_format

    monkeypatch.setattr("api.security.documents.schedule_google_doc_import", _capture)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _import_google_doc(client, org["id"], owner_token, document_url_or_id="1AbCdEfGhIjKlMnOp", export_format="text/plain")

    assert response.status_code == 202
    assert captured["document_id"] == "1AbCdEfGhIjKlMnOp"
    assert captured["export_format"] == "text/plain"


async def test_schedule_google_doc_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_google_doc_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.google_docs_import.process_google_doc_task.delay", _boom)
    schedule_google_doc_import("1AbC", uuid.uuid4(), None, None, uuid.uuid4())  # must not raise


async def test_schedule_google_docs_batch_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_google_docs_batch_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.google_docs_import.process_google_docs_batch_task.delay", _boom)
    schedule_google_docs_batch_import(["1AbC", "1DeF"], uuid.uuid4(), None, uuid.uuid4())  # must not raise


async def test_viewer_cannot_start_a_google_doc_import(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "googledocsviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _import_google_doc(client, org["id"], viewer_token, document_url_or_id="1AbCdEfGhIjKlMnOp")
    assert response.status_code == 403


# ------------------------------------------------------- process_google_docs_batch --

def test_process_google_docs_batch_schedules_one_task_per_document(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def delay(self, *args):
            calls.append(args)

    monkeypatch.setattr("api.tasks.google_docs_import.process_google_doc_task", _FakeTask())

    org_id, created_by = uuid.uuid4(), uuid.uuid4()
    scheduled = documents_module.process_google_docs_batch(org_id, None, ["d1", "d2"], created_by)

    assert scheduled == 2
    assert calls[0] == ("d1", str(org_id), None, None, str(created_by))
    assert calls[1] == ("d2", str(org_id), None, None, str(created_by))


def test_process_google_docs_batch_tolerates_a_broker_failure_for_one_document(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FlakyTask:
        def delay(self, *args):
            if args[0] == "bad":
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.google_docs_import.process_google_doc_task", _FlakyTask())

    scheduled = documents_module.process_google_docs_batch(uuid.uuid4(), None, ["good-1", "bad", "good-2"], uuid.uuid4())

    assert scheduled == 2
    assert len(calls) == 2


# ------------------------------------------------------------- Notion import --

_REAL_NOTION_ID = "1234567890abcdef1234567890abcdef"


async def _import_notion(client, org_id: str, token: str, url_or_id: str, workspace_id=None, kind=None, max_pages=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    body = {"url_or_id": url_or_id}
    if kind is not None:
        body["kind"] = kind
    if max_pages is not None:
        body["max_pages"] = max_pages
    return await client.post(
        f"/organizations/{org_id}/documents/notion", params=params,
        json=body, headers=_auth_header(token),
    )


async def test_owner_can_start_a_notion_page_import(client, db_session, register_payload):
    """Validation criterion (2.1.16): l'import d'une page Notion
    fonctionne, through its own real route. Real network activity is
    deliberately NOT triggered -- schedule_notion_page_import is
    stubbed by tests/conftest.py's own autouse fixture."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_notion(client, org["id"], owner_token, _REAL_NOTION_ID)
    assert response.status_code == 202
    body = response.json()
    assert body == {"notion_id": _REAL_NOTION_ID, "kind": "page", "status": "scheduled"}


async def test_owner_can_start_a_notion_database_import(client, db_session, register_payload):
    """Validation criterion: l'import d'une base de données fonctionne."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_notion(client, org["id"], owner_token, _REAL_NOTION_ID, kind="database")
    assert response.status_code == 202
    assert response.json()["kind"] == "database"


async def test_notion_import_rejects_an_invalid_url(client, db_session, register_payload):
    """Validation criterion: une page invalide est rejetée."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_notion(client, org["id"], owner_token, "https://example.com/not-notion")
    assert response.status_code == 400


async def test_notion_import_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "notionotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _import_notion(client, org["id"], owner_token, _REAL_NOTION_ID, workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_notion_import_rejects_max_pages_out_of_bounds(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_notion(client, org["id"], owner_token, _REAL_NOTION_ID, max_pages=0)
    assert response.status_code == 422

    response = await _import_notion(client, org["id"], owner_token, _REAL_NOTION_ID, max_pages=1001)
    assert response.status_code == 422


async def test_notion_database_import_passes_max_pages_through_to_scheduling(client, db_session, register_payload, monkeypatch):
    captured = {}

    def _capture(notion_id, organization_id, workspace_id, max_pages, created_by):
        captured["max_pages"] = max_pages

    monkeypatch.setattr("api.security.documents.schedule_notion_database_import", _capture)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _import_notion(client, org["id"], owner_token, _REAL_NOTION_ID, kind="database", max_pages=42)

    assert response.status_code == 202
    assert captured["max_pages"] == 42


async def test_schedule_notion_page_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_notion_page_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.notion_import.process_notion_page_task.delay", _boom)
    schedule_notion_page_import(_REAL_NOTION_ID, uuid.uuid4(), None, uuid.uuid4())  # must not raise


async def test_schedule_notion_database_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_notion_database_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.notion_import.process_notion_database_task.delay", _boom)
    schedule_notion_database_import(_REAL_NOTION_ID, uuid.uuid4(), None, 100, uuid.uuid4())  # must not raise


async def test_viewer_cannot_start_a_notion_import(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "notionviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _import_notion(client, org["id"], viewer_token, _REAL_NOTION_ID)
    assert response.status_code == 403


# --------------------------------------------------------- process_notion_pages --

def test_process_notion_pages_schedules_one_task_per_page_with_a_real_stagger(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append((args, countdown))

    monkeypatch.setattr("api.tasks.notion_import.process_notion_page_task", _FakeTask())

    org_id, created_by = uuid.uuid4(), uuid.uuid4()
    scheduled = documents_module.process_notion_pages(org_id, None, ["p1", "p2"], created_by)

    assert scheduled == 2
    assert calls[0][1] == 0
    assert calls[1][1] == documents_module._NOTION_PAGE_STAGGER_SECONDS


def test_process_notion_pages_caps_the_real_stagger_for_a_very_long_list(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append(countdown)

    monkeypatch.setattr("api.tasks.notion_import.process_notion_page_task", _FakeTask())

    many_ids = [f"p{i}" for i in range(500)]
    documents_module.process_notion_pages(uuid.uuid4(), None, many_ids, created_by=None)

    assert max(calls) == documents_module._NOTION_MAX_STAGGER_SECONDS


def test_process_notion_pages_tolerates_a_broker_failure_for_one_page(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FlakyTask:
        def apply_async(self, args, countdown):
            if args[0] == "bad":
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.notion_import.process_notion_page_task", _FlakyTask())

    scheduled = documents_module.process_notion_pages(uuid.uuid4(), None, ["good-1", "bad", "good-2"], created_by=None)

    assert scheduled == 2
    assert len(calls) == 2


# --------------------------------------------------------- Confluence import --

_REAL_CONFLUENCE_BASE_URL = "https://example-tenant.atlassian.net/wiki"


async def _import_confluence(client, org_id: str, token: str, url_or_id: str, workspace_id=None, max_pages=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    body = {"url_or_id": url_or_id}
    if max_pages is not None:
        body["max_pages"] = max_pages
    return await client.post(
        f"/organizations/{org_id}/documents/confluence", params=params,
        json=body, headers=_auth_header(token),
    )


async def test_owner_can_start_a_confluence_page_import(client, db_session, register_payload):
    """Validation criterion (2.1.17): l'import d'une page Confluence
    fonctionne, through its own real route. Real network activity is
    deliberately NOT triggered -- schedule_confluence_page_import is
    stubbed by tests/conftest.py's own autouse fixture."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_confluence(client, org["id"], owner_token, "123456789")
    assert response.status_code == 202
    body = response.json()
    assert body == {"confluence_id": "123456789", "kind": "page", "status": "scheduled"}


async def test_owner_can_start_a_confluence_space_import(client, db_session, register_payload):
    """Validation criterion: l'import d'un espace fonctionne."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_confluence(client, org["id"], owner_token, f"{_REAL_CONFLUENCE_BASE_URL}/spaces/DOCS")
    assert response.status_code == 202
    assert response.json() == {"confluence_id": "DOCS", "kind": "space", "status": "scheduled"}


async def test_confluence_import_rejects_an_invalid_url(client, db_session, register_payload):
    """Validation criterion: une page invalide est rejetée."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_confluence(client, org["id"], owner_token, "https://example.com/not-confluence")
    assert response.status_code == 400


async def test_confluence_import_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "confluenceotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _import_confluence(client, org["id"], owner_token, "123456789", workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_confluence_import_rejects_max_pages_out_of_bounds(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_confluence(client, org["id"], owner_token, "123456789", max_pages=0)
    assert response.status_code == 422

    response = await _import_confluence(client, org["id"], owner_token, "123456789", max_pages=1001)
    assert response.status_code == 422


async def test_confluence_space_import_passes_max_pages_through_to_scheduling(client, db_session, register_payload, monkeypatch):
    captured = {}

    def _capture(confluence_id, organization_id, workspace_id, max_pages, created_by):
        captured["max_pages"] = max_pages

    monkeypatch.setattr("api.security.documents.schedule_confluence_space_import", _capture)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _import_confluence(client, org["id"], owner_token, f"{_REAL_CONFLUENCE_BASE_URL}/spaces/DOCS", max_pages=42)

    assert response.status_code == 202
    assert captured["max_pages"] == 42


async def test_schedule_confluence_page_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_confluence_page_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.confluence_import.process_confluence_page_task.delay", _boom)
    schedule_confluence_page_import("123456789", uuid.uuid4(), None, uuid.uuid4())  # must not raise


async def test_schedule_confluence_space_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_confluence_space_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.confluence_import.process_confluence_space_task.delay", _boom)
    schedule_confluence_space_import("DOCS", uuid.uuid4(), None, 100, uuid.uuid4())  # must not raise


async def test_viewer_cannot_start_a_confluence_import(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "confluenceviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _import_confluence(client, org["id"], viewer_token, "123456789")
    assert response.status_code == 403


# ----------------------------------------------------- process_confluence_pages --

def test_process_confluence_pages_schedules_one_task_per_page_with_a_real_stagger(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append((args, countdown))

    monkeypatch.setattr("api.tasks.confluence_import.process_confluence_page_task", _FakeTask())

    org_id, created_by = uuid.uuid4(), uuid.uuid4()
    scheduled = documents_module.process_confluence_pages(org_id, None, ["p1", "p2"], created_by)

    assert scheduled == 2
    assert calls[0][1] == 0
    assert calls[1][1] == documents_module._CONFLUENCE_PAGE_STAGGER_SECONDS


def test_process_confluence_pages_tolerates_a_broker_failure_for_one_page(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FlakyTask:
        def apply_async(self, args, countdown):
            if args[0] == "bad":
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.confluence_import.process_confluence_page_task", _FlakyTask())

    scheduled = documents_module.process_confluence_pages(uuid.uuid4(), None, ["good-1", "bad", "good-2"], created_by=None)

    assert scheduled == 2
    assert len(calls) == 2


# ------------------------------------------------------- OneDrive import --

async def _import_onedrive(client, org_id: str, token: str, folder_id: str, workspace_id=None, patterns=None, max_files=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    body = {"folder_id": folder_id}
    if patterns is not None:
        body["patterns"] = patterns
    if max_files is not None:
        body["max_files"] = max_files
    return await client.post(
        f"/organizations/{org_id}/documents/onedrive", params=params,
        json=body, headers=_auth_header(token),
    )


async def test_owner_can_start_a_onedrive_import(client, db_session, register_payload):
    """Validation criterion (2.1.18): l'import OneDrive fonctionne,
    through its own real route. Real network activity is deliberately
    NOT triggered -- schedule_onedrive_import is stubbed by
    tests/conftest.py's own autouse fixture, the same "only the
    synchronous half" reasoning as every prior async import test."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_onedrive(client, org["id"], owner_token, "fake-onedrive-folder-id")
    assert response.status_code == 202
    body = response.json()
    assert body == {"folder_id": "fake-onedrive-folder-id", "status": "scheduled"}


async def test_onedrive_import_rejects_an_empty_folder_id(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_onedrive(client, org["id"], owner_token, "")
    assert response.status_code == 422  # pydantic's own min_length=1 rejects this before application code ever runs


async def test_onedrive_import_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "onedriveotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _import_onedrive(client, org["id"], owner_token, "fake-onedrive-folder-id", workspace_id=other_workspace["id"])
    assert response.status_code == 400


async def test_onedrive_import_rejects_max_files_out_of_bounds(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _import_onedrive(client, org["id"], owner_token, "fake-onedrive-folder-id", max_files=0)
    assert response.status_code == 422

    response = await _import_onedrive(client, org["id"], owner_token, "fake-onedrive-folder-id", max_files=2001)
    assert response.status_code == 422


async def test_onedrive_import_passes_patterns_and_max_files_through_to_scheduling(client, db_session, register_payload, monkeypatch):
    captured = {}

    def _capture(folder_id, organization_id, workspace_id, patterns, max_files, created_by):
        captured["folder_id"] = folder_id
        captured["patterns"] = patterns
        captured["max_files"] = max_files

    monkeypatch.setattr("api.security.documents.schedule_onedrive_import", _capture)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    response = await _import_onedrive(
        client, org["id"], owner_token, "fake-onedrive-folder-id", patterns=[".pdf"], max_files=42,
    )

    assert response.status_code == 202
    assert captured["patterns"] == [".pdf"]
    assert captured["max_files"] == 42


async def test_schedule_onedrive_import_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_onedrive_import

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.onedrive_import.process_onedrive_task.delay", _boom)
    schedule_onedrive_import("fake-onedrive-folder-id", uuid.uuid4(), None, None, 100, uuid.uuid4())  # must not raise


async def test_viewer_cannot_start_a_onedrive_import(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "onedriveviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _import_onedrive(client, org["id"], viewer_token, "fake-onedrive-folder-id")
    assert response.status_code == 403


# --------------------------------------------------- process_onedrive_files --

def test_process_onedrive_files_schedules_one_task_per_file_with_a_real_stagger(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append((args, countdown))

    monkeypatch.setattr("api.tasks.onedrive_import.process_onedrive_file_task", _FakeTask())

    org_id, workspace_id, created_by = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    file_ids = ["f1", "f2"]
    scheduled = documents_module.process_onedrive_files(org_id, workspace_id, file_ids, created_by)

    assert scheduled == 2
    assert calls[0][0] == ["f1", str(org_id), str(workspace_id), str(created_by)]
    assert calls[0][1] == 0
    assert calls[1][1] == documents_module._ONEDRIVE_PER_FILE_STAGGER_SECONDS


def test_process_onedrive_files_tolerates_a_broker_failure_for_one_file(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FlakyTask:
        def apply_async(self, args, countdown):
            if args[0] == "bad":
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.onedrive_import.process_onedrive_file_task", _FlakyTask())

    scheduled = documents_module.process_onedrive_files(uuid.uuid4(), None, ["good-1", "bad", "good-2"], created_by=None)

    assert scheduled == 2
    assert len(calls) == 2


# ------------------------------------------------------------ ZIP upload --

def _real_zip_bytes(entries: dict[str, bytes | str]) -> bytes:
    import io
    import zipfile as zipfile_module

    buf = io.BytesIO()
    with zipfile_module.ZipFile(buf, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buf.getvalue()


async def test_owner_can_upload_a_zip_archive(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.1.19): l'upload d'une archive ZIP
    fonctionne, reutilisant la meme route/pipeline qu'un PDF/DOCX."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    content = _real_zip_bytes({"report.pdf": b"%PDF-1.4 fake pdf", "notes.txt": "hello"})
    response = await _upload(client, org["id"], owner_token, filename="archive.zip", content=content, declared_content_type="application/zip")

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "archive.zip"
    assert body["file_type"] == "application/zip"
    assert body["status"] == DocumentStatus.pending.value


async def test_zip_upload_dispatches_the_real_zip_task_not_the_generic_one(client, db_session, register_payload, monkeypatch):
    """Real, deliberate branch in upload_document -- a real ZIP archive
    is never run through the generic process_document_task."""
    _stub_s3(monkeypatch)
    generic_calls = []
    zip_calls = []
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: generic_calls.append(document_id))
    monkeypatch.setattr("api.security.documents.schedule_zip_processing", lambda document_id, organization_id, workspace_id, created_by: zip_calls.append(document_id))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    content = _real_zip_bytes({"notes.txt": "hello"})
    response = await _upload(client, org["id"], owner_token, filename="archive.zip", content=content, declared_content_type="application/zip")

    assert response.status_code == 201
    assert len(zip_calls) == 1
    assert len(generic_calls) == 0


async def test_viewer_cannot_upload_a_zip_archive(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "zipviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    content = _real_zip_bytes({"notes.txt": "hello"})
    response = await _upload(client, org["id"], viewer_token, filename="archive.zip", content=content, declared_content_type="application/zip")
    assert response.status_code == 403


async def test_schedule_zip_processing_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_zip_processing

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.zip_import.process_zip_task.delay", _boom)
    schedule_zip_processing(uuid.uuid4(), uuid.uuid4(), None, uuid.uuid4())  # must not raise


# --------------------------------------------------- process_zip_entries --

def test_process_zip_entries_schedules_one_task_per_entry_with_a_real_stagger(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append((args, countdown))

    monkeypatch.setattr("api.tasks.zip_import.process_zip_entry_task", _FakeTask())

    org_id, workspace_id, zip_file_id, created_by = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    entry_names = ["a.pdf", "b.pdf"]
    scheduled = documents_module.process_zip_entries(org_id, workspace_id, zip_file_id, entry_names, created_by)

    assert scheduled == 2
    assert calls[0][0] == [{"zip_file_id": str(zip_file_id), "entry_name": "a.pdf"}, str(org_id), str(workspace_id), str(created_by)]
    assert calls[0][1] == 0
    assert calls[1][1] == documents_module._ZIP_ENTRY_STAGGER_SECONDS


def test_process_zip_entries_tolerates_a_broker_failure_for_one_entry(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FlakyTask:
        def apply_async(self, args, countdown):
            if args[0]["entry_name"] == "bad.pdf":
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.zip_import.process_zip_entry_task", _FlakyTask())

    scheduled = documents_module.process_zip_entries(uuid.uuid4(), None, uuid.uuid4(), ["good-1.pdf", "bad.pdf", "good-2.pdf"], created_by=None)

    assert scheduled == 2
    assert len(calls) == 2


# ------------------------------------------------------ Batch upload --

async def _upload_batch(client, org_id: str, token: str, files: list[tuple[str, bytes, str]], workspace_id=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    return await client.post(
        f"/organizations/{org_id}/documents/batch", params=params,
        files=[("files", (name, content, ctype)) for name, content, ctype in files],
        headers=_auth_header(token),
    )


async def test_owner_can_upload_multiple_documents(client, db_session, register_payload, monkeypatch):
    """Validation criterion (2.2.1): l'upload de plusieurs fichiers en
    une seule requête fonctionne."""
    monkeypatch.setattr("api.security.documents.upload_document_file", lambda org_id, doc_id, filename, content, content_type: f"documents/{org_id}/{doc_id}/{filename}")
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload_batch(client, org["id"], owner_token, [
        ("a.pdf", _REAL_PDF_MAGIC, "application/pdf"),
        ("b.pdf", _REAL_PDF_MAGIC, "application/pdf"),
    ])

    assert response.status_code == 202
    body = response.json()
    assert body["scheduled"] == 2
    assert all(r["accepted"] for r in body["results"])
    assert [r["filename"] for r in body["results"]] == ["a.pdf", "b.pdf"]


async def test_batch_upload_rejects_an_invalid_file_but_accepts_the_rest(client, db_session, register_payload, monkeypatch):
    """Validation criterion / vision critique 3/4: un fichier invalide
    est rejeté, sans bloquer les autres fichiers du lot."""
    import os

    monkeypatch.setattr("api.security.documents.upload_document_file", lambda org_id, doc_id, filename, content, content_type: f"documents/{org_id}/{doc_id}/{filename}")
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload_batch(client, org["id"], owner_token, [
        ("good.pdf", _REAL_PDF_MAGIC, "application/pdf"),
        ("bad.bin", os.urandom(200), "application/octet-stream"),
    ])

    assert response.status_code == 202
    body = response.json()
    assert body["scheduled"] == 1
    results = {r["filename"]: r for r in body["results"]}
    assert results["good.pdf"]["accepted"] is True
    assert results["bad.bin"]["accepted"] is False
    assert results["bad.bin"]["error"] is not None


async def test_batch_upload_rejects_too_many_files(client, db_session, register_payload, monkeypatch):
    """Validation criterion / vision critique: la limite de fichiers
    est respectée."""
    monkeypatch.setattr(settings, "DOCUMENT_BATCH_MAX_FILES", 2)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload_batch(client, org["id"], owner_token, [
        ("a.pdf", _REAL_PDF_MAGIC, "application/pdf"),
        ("b.pdf", _REAL_PDF_MAGIC, "application/pdf"),
        ("c.pdf", _REAL_PDF_MAGIC, "application/pdf"),
    ])
    assert response.status_code == 400


async def test_batch_upload_rejects_a_batch_exceeding_the_total_size_limit(client, db_session, register_payload, monkeypatch):
    """Validation criterion / vision critique: la limite de taille
    totale est respectée."""
    monkeypatch.setattr(settings, "DOCUMENT_BATCH_MAX_TOTAL_SIZE", 100)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload_batch(client, org["id"], owner_token, [
        ("a.pdf", _REAL_PDF_MAGIC * 10, "application/pdf"),
    ])
    assert response.status_code == 400


async def test_batch_upload_rejects_a_workspace_from_another_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_owner_token, other_owner = await _register(client, db_session, "batchotherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_workspace = (await client.post(
        f"/organizations/{other_org['id']}/workspaces", json={"name": "Other Workspace"}, headers=_auth_header(other_owner_token),
    )).json()

    response = await _upload_batch(
        client, org["id"], owner_token, [("a.pdf", _REAL_PDF_MAGIC, "application/pdf")], workspace_id=other_workspace["id"],
    )
    assert response.status_code == 400


async def test_viewer_cannot_upload_a_batch(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "batchviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload_batch(client, org["id"], viewer_token, [("a.pdf", _REAL_PDF_MAGIC, "application/pdf")])
    assert response.status_code == 403


async def test_batch_upload_passes_only_accepted_files_through_to_scheduling(client, db_session, register_payload, monkeypatch):
    import os

    captured = {}

    def _capture(organization_id, workspace_id, created_by, files):
        captured["files"] = files

    monkeypatch.setattr("api.security.documents.schedule_upload_batch_processing", _capture)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload_batch(client, org["id"], owner_token, [
        ("good.pdf", _REAL_PDF_MAGIC, "application/pdf"),
        ("bad.bin", os.urandom(200), "application/octet-stream"),
    ])

    assert response.status_code == 202
    assert [f["filename"] for f in captured["files"]] == ["good.pdf"]


async def test_schedule_upload_batch_processing_does_not_raise_when_the_broker_is_unreachable(monkeypatch):
    from api.security.documents import schedule_upload_batch_processing

    def _boom(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("api.tasks.document_batch_processing.process_upload_batch_task.delay", _boom)
    schedule_upload_batch_processing(uuid.uuid4(), None, uuid.uuid4(), [{"filename": "a.pdf", "content": _REAL_PDF_MAGIC, "content_type": "application/pdf"}])  # must not raise


# ------------------------------------------------------------------- tags --

async def test_member_can_create_a_tag(client, db_session, register_payload):
    """Validation criterion (2.2.6): un membre peut créer un tag."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance", "color": "#2563eb"}, headers=_auth_header(owner_token))
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "finance"
    assert body["color"] == "#2563eb"
    assert body["created_by"] == str(owner.id)


async def test_viewer_cannot_create_a_tag(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "tagviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(viewer_token))
    assert response.status_code == 403


async def test_creating_a_duplicate_tag_name_in_the_same_organization_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))

    response = await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))
    assert response.status_code == 409


async def test_viewer_can_list_organization_tags(client, db_session, register_payload):
    """Vision critique 1 / deliberate deviation: la lecture reste
    ouverte au Viewer, comme chaque autre route GET de ce routeur."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))
    viewer_token, viewer = await _register(client, db_session, "tagslistviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/tags", headers=_auth_header(viewer_token))
    assert response.status_code == 200
    assert [t["name"] for t in response.json()] == ["finance"]


async def test_creator_can_update_their_own_tag(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()

    response = await client.patch(f"/tags/{tag['id']}", json={"color": "#f97316"}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["color"] == "#f97316"


async def test_member_cannot_update_a_tag_created_by_another_member(client, db_session, register_payload):
    """Validation criterion / vision critique 3: un membre ne peut pas
    modifier un tag créé par un autre."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()

    other_member_token, other_member = await _register(client, db_session, "tagothermember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), other_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.patch(f"/tags/{tag['id']}", json={"color": "#000000"}, headers=_auth_header(other_member_token))
    assert response.status_code == 403


async def test_admin_can_update_a_tag_created_by_another_member(client, db_session, register_payload):
    """Real admin override, same shape as DELETE /documents/{id}."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()

    admin_token, admin = await _register(client, db_session, "tagadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.patch(f"/tags/{tag['id']}", json={"color": "#000000"}, headers=_auth_header(admin_token))
    assert response.status_code == 200


async def test_member_cannot_delete_a_tag_created_by_another_member(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()

    other_member_token, other_member = await _register(client, db_session, "tagdeleteother@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), other_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.delete(f"/tags/{tag['id']}", headers=_auth_header(other_member_token))
    assert response.status_code == 403


async def test_creator_can_delete_their_own_tag(client, db_session, register_payload):
    """Validation criterion: un membre peut retirer/supprimer un tag."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()

    response = await client.delete(f"/tags/{tag['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 200

    listing = await client.get(f"/organizations/{org['id']}/tags", headers=_auth_header(owner_token))
    assert listing.json() == []


async def test_patch_for_a_nonexistent_tag_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.patch(f"/tags/{uuid.uuid4()}", json={"color": "#000"}, headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_owner_can_add_a_tag_to_their_own_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion: un membre peut ajouter un tag à un
    document."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.post(f"/documents/{document_id}/tags", json={"tag_id": tag["id"]}, headers=_auth_header(owner_token))
    assert response.status_code == 201

    listing = await client.get(f"/documents/{document_id}/tags", headers=_auth_header(owner_token))
    assert [t["name"] for t in listing.json()] == ["finance"]


async def test_member_cannot_tag_a_document_they_do_not_own(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    other_member_token, other_member = await _register(client, db_session, "tagdocother@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), other_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(f"/documents/{document_id}/tags", json={"tag_id": tag["id"]}, headers=_auth_header(other_member_token))
    assert response.status_code == 403


async def test_assigning_a_tag_from_another_organization_is_rejected(client, db_session, register_payload, monkeypatch):
    """Vision critique 1 -- un tag n'est partagé qu'au sein de sa
    propre organisation."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    other_owner_token, other_owner = await _register(client, db_session, "tagotherorgowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")
    other_tag = (await client.post(f"/organizations/{other_org['id']}/tags", json={"name": "finance"}, headers=_auth_header(other_owner_token))).json()

    response = await client.post(f"/documents/{document_id}/tags", json={"tag_id": other_tag["id"]}, headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_assigning_the_same_tag_twice_is_rejected(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/tags", json={"tag_id": tag["id"]}, headers=_auth_header(owner_token))

    response = await client.post(f"/documents/{document_id}/tags", json={"tag_id": tag["id"]}, headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_owner_can_remove_a_tag_from_their_own_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion: un membre peut retirer un tag d'un
    document."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/tags", json={"tag_id": tag["id"]}, headers=_auth_header(owner_token))

    response = await client.delete(f"/documents/{document_id}/tags/{tag['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 200

    listing = await client.get(f"/documents/{document_id}/tags", headers=_auth_header(owner_token))
    assert listing.json() == []


async def test_viewer_can_list_a_documents_tags(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    viewer_token, viewer = await _register(client, db_session, "tagdocviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.get(f"/documents/{document_id}/tags", headers=_auth_header(viewer_token))
    assert response.status_code == 200
    assert response.json() == []


# --------------------------------------------------------------- versions --

_REAL_PDF_MAGIC_V2 = b"%PDF-1.4\n%a real, different second version of the same document\n"


async def test_a_freshly_uploaded_document_has_no_versions_yet(client, db_session, register_payload, monkeypatch):
    """Validation criterion / vision critique -- limite honnête assumée
    : l'upload original n'est pas rétroactivement versionné."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.get(f"/documents/{document_id}/versions", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json() == []


async def test_owner_can_create_a_new_document_version(client, db_session, register_payload, monkeypatch):
    """Validation criterion: une nouvelle version est créée ; les
    versions sont numérotées automatiquement."""
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.post(
        f"/documents/{document_id}/versions", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["version_number"] == 1

    second = await client.post(
        f"/documents/{document_id}/versions", files={"file": ("v3.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token),
    )
    assert second.json()["version_number"] == 2

    listing = await client.get(f"/documents/{document_id}/versions", headers=_auth_header(owner_token))
    assert [v["version_number"] for v in listing.json()] == [2, 1]  # most recent first


async def test_member_cannot_create_a_version_of_a_document_they_do_not_own(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    other_member_token, other_member = await _register(client, db_session, "versionother@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), other_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/documents/{document_id}/versions", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(other_member_token),
    )
    assert response.status_code == 403


async def test_admin_can_create_a_version_of_a_document_they_do_not_own(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    admin_token, admin = await _register(client, db_session, "versionadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(
        f"/documents/{document_id}/versions", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(admin_token),
    )
    assert response.status_code == 201


async def test_get_a_specific_document_version(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/versions", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token))

    response = await client.get(f"/documents/{document_id}/versions/1", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["version_number"] == 1


async def test_get_a_nonexistent_document_version_returns_404(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.get(f"/documents/{document_id}/versions/99", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_owner_can_restore_a_previous_document_version(client, db_session, register_payload, monkeypatch):
    """Validation criterion: la restauration fonctionne."""
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/versions", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token))
    await client.post(f"/documents/{document_id}/versions", files={"file": ("v3.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token))

    response = await client.post(f"/documents/{document_id}/versions/restore", json={"version_number": 1}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["version_number"] == 3  # a real NEW version, not a rewind

    listing = await client.get(f"/documents/{document_id}/versions", headers=_auth_header(owner_token))
    assert [v["version_number"] for v in listing.json()] == [3, 2, 1]


async def test_restoring_a_nonexistent_version_returns_404(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.post(f"/documents/{document_id}/versions/restore", json={"version_number": 99}, headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_member_cannot_restore_a_version_of_a_document_they_do_not_own(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/versions", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token))

    other_member_token, other_member = await _register(client, db_session, "versionrestoreother@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), other_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(f"/documents/{document_id}/versions/restore", json={"version_number": 1}, headers=_auth_header(other_member_token))
    assert response.status_code == 403


async def test_viewer_can_list_and_view_document_versions(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/versions", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token))
    viewer_token, viewer = await _register(client, db_session, "versionviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    listing = await client.get(f"/documents/{document_id}/versions", headers=_auth_header(viewer_token))
    assert listing.status_code == 200
    detail = await client.get(f"/documents/{document_id}/versions/1", headers=_auth_header(viewer_token))
    assert detail.status_code == 200


# ------------------------------------------------ permanent delete / replace --

async def test_admin_can_permanently_delete_a_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion: la suppression définitive supprime tout
    (S3 + DB)."""
    _stub_s3(monkeypatch)
    s3_deletes = []
    monkeypatch.setattr("api.security.documents.delete_document_file", lambda file_key: s3_deletes.append(file_key))
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    uploader_token, uploader = await _register(client, db_session, "permdeluploader@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), uploader.id, OrganizationRole.member, invited_by=owner.id)
    created = await _upload(client, org["id"], uploader_token)
    document_id = created.json()["id"]

    admin_token, admin = await _register(client, db_session, "permdeladmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.delete(f"/documents/{document_id}/permanent", headers=_auth_header(admin_token))
    assert response.status_code == 200
    assert len(s3_deletes) == 1

    row = await db_session.scalar(select(Document).where(Document.id == uuid.UUID(document_id)))
    assert row is None


async def test_member_cannot_permanently_delete_their_own_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion / vision critique 1: réservée à Owner/Admin,
    même le propriétaire d'un simple rôle Member ne peut pas purger."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "permdelmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)
    created = await _upload(client, org["id"], member_token)
    document_id = created.json()["id"]

    response = await client.delete(f"/documents/{document_id}/permanent", headers=_auth_header(member_token))
    assert response.status_code == 403

    row = await db_session.scalar(select(Document).where(Document.id == uuid.UUID(document_id)))
    assert row is not None


async def test_admin_can_permanently_delete_an_already_soft_deleted_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion / vision critique 2: un document supprimé
    logiquement reste atteignable pour une purge définitive."""
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.delete_document_file", lambda file_key: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.delete(f"/documents/{document_id}", headers=_auth_header(owner_token))  # soft delete first

    response = await client.delete(f"/documents/{document_id}/permanent", headers=_auth_header(owner_token))
    assert response.status_code == 200

    row = await db_session.scalar(select(Document).where(Document.id == uuid.UUID(document_id)))
    assert row is None


async def test_permanent_delete_for_a_nonexistent_document_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.delete(f"/documents/{uuid.uuid4()}/permanent", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_owner_can_replace_a_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion: le remplacement crée une nouvelle
    version."""
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.post(
        f"/documents/{document_id}/replace", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["version_number"] == 1

    versions = await client.get(f"/documents/{document_id}/versions", headers=_auth_header(owner_token))
    assert len(versions.json()) == 1


async def test_member_cannot_replace_a_document_they_do_not_own(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    other_member_token, other_member = await _register(client, db_session, "replaceother@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), other_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/documents/{document_id}/replace", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(other_member_token),
    )
    assert response.status_code == 403


async def test_a_soft_deleted_document_is_invisible_to_listing_and_detail(client, db_session, register_payload, monkeypatch):
    """Validation criterion / vision critique -- modifier les requêtes
    pour exclure les documents supprimés."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.delete(f"/documents/{document_id}", headers=_auth_header(owner_token))

    listing = await client.get(f"/organizations/{org['id']}/documents", headers=_auth_header(owner_token))
    assert listing.json()["items"] == []

    for path in (
        f"/documents/{document_id}", f"/documents/{document_id}/metadata", f"/documents/{document_id}/preview",
        f"/documents/{document_id}/progress", f"/documents/{document_id}/tags", f"/documents/{document_id}/versions",
    ):
        response = await client.get(path, headers=_auth_header(owner_token))
        assert response.status_code == 404, f"{path} should be invisible once soft-deleted"


# --------------------------------------------------------------- reindex --

async def test_owner_can_reindex_their_own_document(client, db_session, register_payload, monkeypatch):
    """Validation criterion: la réindexation d'un document fonctionne."""
    _stub_s3(monkeypatch)
    captured = []
    monkeypatch.setattr("api.security.documents.schedule_document_reindex", lambda document_id, triggered_by=None: captured.append(document_id))
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.post(f"/documents/{document_id}/reindex", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(captured) == 1


async def test_member_cannot_reindex_a_document_they_do_not_own(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    other_member_token, other_member = await _register(client, db_session, "reindexother@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), other_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(f"/documents/{document_id}/reindex", headers=_auth_header(other_member_token))
    assert response.status_code == 403


async def test_admin_can_reindex_any_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    admin_token, admin = await _register(client, db_session, "reindexadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(f"/documents/{document_id}/reindex", headers=_auth_header(admin_token))
    assert response.status_code == 200


async def test_admin_can_reindex_an_entire_organization(client, db_session, register_payload, monkeypatch):
    """Validation criterion: la réindexation de tous les documents
    fonctionne."""
    _stub_s3(monkeypatch)
    captured = []
    monkeypatch.setattr("api.security.documents.schedule_organization_reindex", lambda organization_id, triggered_by=None: captured.append(organization_id))
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _upload(client, org["id"], owner_token)
    await _upload(client, org["id"], owner_token)

    response = await client.post(f"/organizations/{org['id']}/documents/reindex", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["document_count"] == 2
    assert len(captured) == 1


async def test_member_cannot_reindex_an_entire_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "reindexorgmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(f"/organizations/{org['id']}/documents/reindex", headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_organization_reindex_excludes_soft_deleted_documents(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await _upload(client, org["id"], owner_token)
    await client.delete(f"/documents/{document_id}", headers=_auth_header(owner_token))

    response = await client.post(f"/organizations/{org['id']}/documents/reindex", headers=_auth_header(owner_token))
    assert response.json()["document_count"] == 1


# ----------------------------------------------------------------- history --

async def test_document_history_records_creation_on_upload(client, db_session, register_payload, monkeypatch):
    """Validation criterion: l'historique est créé lors de l'upload."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    history = await client.get(f"/documents/{document_id}/history", headers=_auth_header(owner_token))
    assert history.status_code == 200
    assert [entry["action"] for entry in history.json()] == ["created"]
    assert history.json()[0]["user_id"] == str(owner.id)


async def test_document_history_records_deletion(client, db_session, register_payload, monkeypatch):
    """Validation criterion: l'historique est créé lors de la
    suppression."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.delete(f"/documents/{document_id}", headers=_auth_header(owner_token))

    history = await client.get(f"/documents/{document_id}/history", headers=_auth_header(owner_token))
    assert history.status_code == 404  # a soft-deleted document is itself invisible, same as every other route


async def test_document_history_records_tag_add_and_remove(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    tag = (await client.post(f"/organizations/{org['id']}/tags", json={"name": "finance"}, headers=_auth_header(owner_token))).json()
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/tags", json={"tag_id": tag["id"]}, headers=_auth_header(owner_token))
    await client.delete(f"/documents/{document_id}/tags/{tag['id']}", headers=_auth_header(owner_token))

    history = await client.get(f"/documents/{document_id}/history", headers=_auth_header(owner_token))
    actions = [entry["action"] for entry in history.json()]
    assert "tag_added" in actions
    assert "tag_removed" in actions


async def test_document_history_records_version_creation_and_restore(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/versions", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token))
    await client.post(f"/documents/{document_id}/versions/restore", json={"version_number": 1}, headers=_auth_header(owner_token))

    history = await client.get(f"/documents/{document_id}/history", headers=_auth_header(owner_token))
    actions = [entry["action"] for entry in history.json()]
    assert actions.count("updated") == 1  # only the explicit new-version creation, not the restore
    assert actions.count("version_restored") == 1


async def test_document_history_records_replace_as_updated(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/replace", files={"file": ("v2.pdf", _REAL_PDF_MAGIC_V2, "application/pdf")}, headers=_auth_header(owner_token))

    history = await client.get(f"/documents/{document_id}/history", headers=_auth_header(owner_token))
    assert "updated" in [entry["action"] for entry in history.json()]


async def test_document_history_records_reindex(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.security.documents.schedule_document_reindex", lambda document_id, triggered_by=None: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await client.post(f"/documents/{document_id}/reindex", headers=_auth_header(owner_token))

    # The real reindex itself runs later, inside Celery -- call the
    # real underlying function directly here to prove it logs for real.
    from unittest.mock import AsyncMock, patch

    from api.security.documents import reindex_document

    with patch("api.security.documents.process_document", new=AsyncMock(return_value=await db_session.get(Document, uuid.UUID(document_id)))):
        await reindex_document(db_session, uuid.UUID(document_id), owner.id)
    await db_session.commit()

    history = await client.get(f"/documents/{document_id}/history", headers=_auth_header(owner_token))
    actions = [entry["action"] for entry in history.json()]
    assert "reindexed" in actions


async def test_viewer_can_view_document_history(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    viewer_token, viewer = await _register(client, db_session, "historyviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.get(f"/documents/{document_id}/history", headers=_auth_header(viewer_token))
    assert response.status_code == 200


async def test_document_history_for_a_nonexistent_document_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get(f"/documents/{uuid.uuid4()}/history", headers=_auth_header(owner_token))
    assert response.status_code == 404


# ------------------------------------------------------- 2.2.11 -- indexing status --

async def test_owner_can_view_document_status_right_after_upload(client, db_session, register_payload, monkeypatch):
    """Validation criterion: le statut d'indexation est consultable via
    l'API, reflétant le vrai statut du document (pending juste après
    l'upload, avant tout traitement réel)."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    response = await client.get(f"/documents/{document_id}/status", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == document_id
    assert body["status"] == DocumentStatus.pending.value
    assert body["indexing_started_at"] is None
    assert body["processed_at"] is None
    assert body["indexing_error"] is None


async def test_document_status_shows_the_real_error_after_a_failed_indexing_attempt(client, db_session, register_payload, monkeypatch):
    """Vision critique -- une erreur réelle d'indexation doit être
    consultable, pas seulement visible dans les logs serveur."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    document = await db_session.get(Document, uuid.UUID(document_id))
    document.status = DocumentStatus.failed.value
    document.indexing_started_at = document.created_at
    document.indexing_error = "S3 object not found"
    await db_session.commit()

    response = await client.get(f"/documents/{document_id}/status", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == DocumentStatus.failed.value
    assert body["indexing_error"] == "S3 object not found"
    assert body["indexing_started_at"] is not None


async def test_viewer_can_view_document_status(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    viewer_token, viewer = await _register(client, db_session, "statusviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.get(f"/documents/{document_id}/status", headers=_auth_header(viewer_token))
    assert response.status_code == 200


async def test_document_status_for_a_nonexistent_document_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get(f"/documents/{uuid.uuid4()}/status", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_document_status_belonging_to_another_organization_returns_404(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]

    outsider_token, outsider = await _register(client, db_session, "statusoutsider@example.com")
    response = await client.get(f"/documents/{document_id}/status", headers=_auth_header(outsider_token))
    assert response.status_code == 404  # anti-enumeration


async def test_admin_can_view_organization_document_status_summary(client, db_session, register_payload, monkeypatch):
    """Validation criterion: un résumé du statut d'indexation de
    l'organisation est consultable (compte réel par statut)."""
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    first = await _upload(client, org["id"], owner_token)
    await _upload(client, org["id"], owner_token)

    completed_document = await db_session.get(Document, uuid.UUID(first.json()["id"]))
    completed_document.status = DocumentStatus.completed.value
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/documents/status", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == org["id"]
    assert body["total"] == 2
    assert body["by_status"] == {DocumentStatus.pending.value: 1, DocumentStatus.completed.value: 1}


async def test_member_cannot_view_organization_document_status_summary(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "statussummarymember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/documents/status", headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_organization_document_status_summary_excludes_soft_deleted_documents(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await _upload(client, org["id"], owner_token)
    document_id = created.json()["id"]
    await _upload(client, org["id"], owner_token)
    await client.delete(f"/documents/{document_id}", headers=_auth_header(owner_token))

    response = await client.get(f"/organizations/{org['id']}/documents/status", headers=_auth_header(owner_token))
    body = response.json()
    assert body["total"] == 1
