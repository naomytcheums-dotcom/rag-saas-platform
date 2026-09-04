"""
Partie 2.1.19 -- orchestration tests for api/security/documents.py's own
process_zip_archive/import_and_process_zip_archive/import_and_process_zip_entry.

**Unlike every other *_integration.py orchestration test file in this
whole 2.1.10-2.1.19 series, there is no external API to simulate at
all** (see api/services/zip_extraction.py's own module docstring) --
only S3 (a real, genuine ZIP archive's own bytes, `download_document_file`/
`upload_document_file`) is stubbed here, the SAME boundary
tests/test_documents.py's own autouse fixtures already draw for every
other format's own real S3 round trip.
"""

import io
import uuid
import zipfile
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.documents import (
    ZIP_CONTENT_TYPE,
    import_and_process_zip_archive,
    import_and_process_zip_entry,
    process_zip_archive,
)


def _build_real_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("report.pdf", b"%PDF-1.4 fake but real-looking pdf bytes")
        archive.writestr("notes.txt", "hello world")
        archive.writestr("../../etc/passwd", "evil")
    return buf.getvalue()


@pytest.fixture
def _stub_s3(monkeypatch):
    monkeypatch.setattr("api.security.documents.upload_document_file", lambda org_id, doc_id, filename, content, content_type: f"documents/{org_id}/{doc_id}/{filename}")
    monkeypatch.setattr("api.security.documents.download_document_file", lambda file_key: _build_real_zip_bytes())


async def _make_org_and_zip_document(session):
    owner = User(email=f"zip-itest-{uuid.uuid4().hex[:8]}@example.com", hashed_password="irrelevant")
    session.add(owner)
    await session.flush()
    organization = Organization(name="Zip ITest Org", slug=f"zip-itest-{uuid.uuid4().hex[:8]}")
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=owner.id, role=OrganizationRole.owner))

    zip_document = Document(
        organization_id=organization.id, workspace_id=None, name="archive.zip",
        file_key="documents/fake/archive.zip", file_size=1234, file_type=ZIP_CONTENT_TYPE,
        status=DocumentStatus.pending.value, created_by=owner.id,
    )
    session.add(zip_document)
    await session.commit()
    return owner, organization, zip_document


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# --------------------------------------------------------- process_zip_archive --

def test_process_zip_archive_filters_and_schedules_real_matching_entries(tmp_path):
    """Validation criterion: les fichiers extraits sont importés via le
    pipeline existant -- ici, vérifié au niveau du fan-out réel."""
    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("report.pdf", b"%PDF-1.4 fake pdf")
        archive.writestr("notes.txt", "hello")
        archive.writestr("photo.png", b"\x89PNG")

    captured = {}

    def _capture(organization_id, workspace_id, zip_file_id, entry_names, created_by):
        captured["entry_names"] = entry_names
        return len(entry_names)

    zip_file_id, organization_id, created_by = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with patch("api.security.documents.process_zip_entries", side_effect=_capture):
        result = process_zip_archive(organization_id, None, zip_file_id, str(path), [".pdf", ".txt"], 100, 10_000, created_by)

    assert result == {"zip_entries_found": 2, "zip_entries_scheduled": 2}
    assert sorted(captured["entry_names"]) == ["notes.txt", "report.pdf"]


def test_process_zip_archive_enforces_a_real_max_files_cap(tmp_path):
    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for i in range(5):
            archive.writestr(f"file-{i}.txt", "content")

    captured = {}

    def _capture(organization_id, workspace_id, zip_file_id, entry_names, created_by):
        captured["entry_names"] = entry_names
        return len(entry_names)

    with patch("api.security.documents.process_zip_entries", side_effect=_capture):
        result = process_zip_archive(uuid.uuid4(), None, uuid.uuid4(), str(path), None, 2, 10_000, uuid.uuid4())

    assert result == {"zip_entries_found": 5, "zip_entries_scheduled": 2}
    assert len(captured["entry_names"]) == 2


def test_process_zip_archive_raises_for_a_real_corrupt_archive(tmp_path):
    """Validation criterion / vision critique 4: archive corrompue
    gérée."""
    bad_path = tmp_path / "corrupt.zip"
    bad_path.write_bytes(b"PK\x03\x04" + bytes(range(200)))
    with pytest.raises(zipfile.BadZipFile):
        process_zip_archive(uuid.uuid4(), None, uuid.uuid4(), str(bad_path), None, 100, 10_000, uuid.uuid4())


# ----------------------------------------------- import_and_process_zip_archive --

async def test_import_and_process_zip_archive_marks_the_container_completed(db_session, _stub_s3):
    """Validation criterion: l'import d'une archive ZIP fonctionne."""
    owner, organization, zip_document = await _make_org_and_zip_document(db_session)
    captured = {}

    def _capture(organization_id, workspace_id, zip_file_id, entry_names, created_by):
        captured["entry_names"] = entry_names
        return len(entry_names)

    with patch("api.security.documents.process_zip_entries", side_effect=_capture):
        document = await import_and_process_zip_archive(
            db_session, organization.id, None, owner.id, zip_document.id, None, 100,
        )

    assert document.status == DocumentStatus.completed.value
    assert document.metadata_json["zip_entries_found"] == 2  # ../../etc/passwd is excluded (ZipSlip)
    assert document.metadata_json["zip_entries_scheduled"] == 2


async def test_import_and_process_zip_archive_raises_for_a_nonexistent_document(db_session, _stub_s3):
    with pytest.raises(ValueError, match="not a real, existing zip"):
        await import_and_process_zip_archive(db_session, uuid.uuid4(), None, uuid.uuid4(), uuid.uuid4(), None, 100)


async def test_import_and_process_zip_archive_marks_failed_for_a_real_corrupt_download(db_session, monkeypatch):
    monkeypatch.setattr("api.security.documents.download_document_file", lambda file_key: b"PK\x03\x04" + bytes(range(200)))
    owner, organization, zip_document = await _make_org_and_zip_document(db_session)

    document = await import_and_process_zip_archive(db_session, organization.id, None, owner.id, zip_document.id, None, 100)
    assert document.status == DocumentStatus.failed.value
    assert "error" in document.metadata_json


# ------------------------------------------------- import_and_process_zip_entry --

async def test_import_and_process_zip_entry_extracts_and_processes_a_real_entry(db_session, _stub_s3):
    """Validation criterion: un fichier individuel de l'archive est
    importé via le pipeline existant, en tant que document séparé."""
    owner, organization, zip_document = await _make_org_and_zip_document(db_session)

    document = await import_and_process_zip_entry(db_session, organization.id, None, owner.id, zip_document.id, "notes.txt")

    assert document.name == "notes.txt"
    assert document.file_type == "text/plain"
    assert document.id != zip_document.id


async def test_import_and_process_zip_entry_marks_failed_for_a_real_missing_entry(db_session, _stub_s3):
    owner, organization, zip_document = await _make_org_and_zip_document(db_session)

    document = await import_and_process_zip_entry(db_session, organization.id, None, owner.id, zip_document.id, "does-not-exist.pdf")

    assert document.status == DocumentStatus.failed.value
    assert document.metadata_json["zip_entry_name"] == "does-not-exist.pdf"


async def test_import_and_process_zip_entry_raises_for_a_nonexistent_zip_document(db_session, _stub_s3):
    with pytest.raises(ValueError, match="not a real, existing zip"):
        await import_and_process_zip_entry(db_session, uuid.uuid4(), None, uuid.uuid4(), uuid.uuid4(), "notes.txt")
