"""
Partie 2.1.1/2.1.2/2.1.3/2.1.4 -- document upload/list/detail/delete
(PDF, DOCX, TXT, and Markdown). Fast SQLite suite, same tier as
tests/test_custom_domains.py. Both real network dependencies are
mocked throughout: S3 (api/security/documents.py's
upload_document_file/download_document_file) and Celery dispatch
(schedule_document_processing, stubbed by default for the whole file --
see tests/conftest.py's _stub_out_document_processing_scheduling_by_default)
-- no real network call belongs in the fast suite.

The real PDF/DOCX/TXT/Markdown extraction/chunking/embedding pipeline
(process_document) and the real Celery task are tested for real,
against real infrastructure, in tests/test_documents_integration.py.
CASCADE-delete of a document's chunks is tested against real Postgres
in tests/test_postgres_integration.py (SQLite doesn't enforce foreign
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
