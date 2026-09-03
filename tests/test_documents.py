"""
Partie 2.1.1 -- document upload/list/detail/delete. Fast SQLite suite,
same tier as tests/test_custom_domains.py. Both real network
dependencies are mocked throughout: S3 (api/security/documents.py's
upload_document_file/download_document_file) and Celery dispatch
(schedule_document_processing, stubbed by default for the whole file --
see tests/conftest.py's _stub_out_document_processing_scheduling_by_default) --
no real network call belongs in the fast suite.

The real PDF extraction/chunking/embedding pipeline (process_pdf_document)
and the real Celery task are tested for real, against real
infrastructure, in tests/test_documents_integration.py. CASCADE-delete
of a document's chunks is tested against real Postgres in
tests/test_postgres_integration.py (SQLite doesn't enforce foreign keys).
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


def _stub_s3(monkeypatch):
    monkeypatch.setattr("api.security.documents.upload_document_file", lambda org_id, doc_id, filename, content: f"documents/{org_id}/{doc_id}/{filename}")


async def _upload(client, org_id: str, token: str, filename="report.pdf", content=_REAL_PDF_MAGIC, workspace_id=None):
    params = {"workspace_id": str(workspace_id)} if workspace_id else {}
    return await client.post(
        f"/organizations/{org_id}/documents", params=params,
        files={"file": (filename, content, "application/pdf")}, headers=_auth_header(token),
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


async def test_upload_rejects_a_non_pdf_file(client, db_session, register_payload, monkeypatch):
    _stub_s3(monkeypatch)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await _upload(client, org["id"], owner_token, filename="not-a-pdf.txt", content=b"just plain text, not a pdf at all")
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
