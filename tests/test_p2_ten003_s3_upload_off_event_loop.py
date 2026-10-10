"""TEN-003: boto3 is synchronous. Called straight from an async upload path it freezes the whole event loop (every other request of the
worker) for the duration of the S3 round trip, retries included. The S3 write must run off the loop thread. S3 is a fake here."""

import threading
import uuid

from api.models.organization import Organization
from api.security import document_versions, documents


async def _organization(db_session) -> uuid.UUID:
    org = Organization(name="Thread Org", slug=f"thr-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org.id


async def test_a_document_upload_writes_to_s3_off_the_event_loop_thread(db_session, monkeypatch):
    loop_thread = threading.get_ident()
    seen = []

    def fake_upload(org_id, doc_id, filename, content, content_type):
        seen.append(threading.get_ident())
        return f"documents/{org_id}/{doc_id}/{filename}"

    monkeypatch.setattr(documents, "upload_document_file", fake_upload)
    monkeypatch.setattr(documents, "schedule_document_processing", lambda document_id: None)
    org_id = await _organization(db_session)

    document, is_duplicate = await documents.upload_document(db_session, org_id, None, uuid.uuid4(), "notes.txt", b"hello from the thread test")

    assert is_duplicate is False and document.file_key.endswith("notes.txt")
    assert seen and seen[0] != loop_thread, "the S3 write ran on the event loop thread and would freeze every other request"


async def test_a_new_document_version_writes_to_s3_off_the_event_loop_thread(db_session, monkeypatch):
    loop_thread = threading.get_ident()
    seen = []

    def fake_upload(org_id, doc_id, filename, content, content_type):
        seen.append(threading.get_ident())
        return f"documents/{org_id}/{doc_id}/{filename}"

    monkeypatch.setattr(documents, "upload_document_file", lambda *a: "documents/first-key")
    monkeypatch.setattr(documents, "schedule_document_processing", lambda document_id: None)
    monkeypatch.setattr(document_versions, "upload_document_file", fake_upload)
    org_id = await _organization(db_session)
    document, _ = await documents.upload_document(db_session, org_id, None, uuid.uuid4(), "notes.txt", b"first version of the notes")

    await document_versions.create_document_version_from_upload(db_session, document.id, "notes.txt", b"second version of the notes", uuid.uuid4())

    assert seen and seen[0] != loop_thread
