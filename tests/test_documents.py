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
    monkeypatch.setattr("api.security.documents.upload_document_file", lambda org_id, doc_id, filename, content, content_type: f"documents/{org_id}/{doc_id}/{filename}")


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


# --------------------------------------------------------------- deleting --

async def test_creator_can_delete_their_own_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    monkeypatch.setattr("api.routers.documents.delete_document_file", lambda file_key: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "docdeleteself@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)
    created = await _upload(client, org["id"], member_token)
    document_id = created.json()["id"]

    response = await client.delete(f"/documents/{document_id}", headers=_auth_header(member_token))
    assert response.status_code == 200

    row = await db_session.scalar(select(Document).where(Document.id == uuid.UUID(document_id)))
    assert row is None


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
    monkeypatch.setattr("api.routers.documents.delete_document_file", lambda file_key: None)
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
    monkeypatch.setattr("api.routers.documents.delete_document_file", lambda file_key: None)
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


async def test_upload_rejects_a_zip_file_that_is_not_a_real_docx(client, db_session, register_payload, monkeypatch):
    """A plain ZIP (or an XLSX/PPTX, which share the exact same leading
    magic bytes as DOCX) must still be rejected -- the ZIP signature
    alone isn't enough, api/services/document_storage.py's
    _is_real_docx also confirms word/document.xml is present."""
    import io
    import zipfile

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("some_file.txt", "just a plain zip, not a docx")
    response = await _upload(client, org["id"], owner_token, filename="fake.docx", content=buffer.getvalue())
    assert response.status_code == 400


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


async def test_upload_rejects_a_zip_file_that_is_not_a_real_epub(client, db_session, register_payload, monkeypatch):
    """Same "content over declared name" rule as DOCX's own equivalent
    test -- a real ZIP that simply isn't an EPUB (no spec-mandated
    `mimetype` entry) is rejected, not silently accepted just because
    it happens to be a ZIP."""
    import io
    import zipfile

    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("hello.txt", "just a random zip, not an epub")

    response = await _upload(client, org["id"], owner_token, filename="fake.epub", content=buffer.getvalue())
    assert response.status_code == 400


async def test_viewer_cannot_upload_an_epub_document(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    viewer_token, viewer = await _register(client, db_session, "epubviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await _upload(client, org["id"], viewer_token, filename="book.epub", content=_real_epub_bytes())
    assert response.status_code == 403
