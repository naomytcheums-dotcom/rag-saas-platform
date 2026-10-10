"""TEN-005: the uploaded file name is untrusted input and must never become a raw S3 key segment (accents and `..` gave 502, and a name could
inject path segments into the tenant's prefix). The S3 client is a fake here: no network."""

import re
import uuid

import pytest

from api.services import document_storage
from api.services.document_storage import safe_object_name, upload_document_file, upload_media_file

ORG, DOC = uuid.uuid4(), uuid.uuid4()


class _FakeS3:
    def __init__(self):
        self.keys = []

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.keys.append(Key)


@pytest.fixture
def fake_s3(monkeypatch):
    fake = _FakeS3()
    monkeypatch.setattr(document_storage, "_client", lambda: fake)
    return fake


@pytest.mark.parametrize("filename, expected", [
    ("report.pdf", "report.pdf"),
    ("plain name 2026.txt", "plain_name_2026.txt"),
    ("résumé final.txt", "resume_final.txt"),
    ("../../etc/passwd.txt", "passwd.txt"),
    ("..\\..\\windows\\win.txt", "win.txt"),
    ("<script>alert(1)</script>.txt", "script.txt"),
    ("名前.txt", "file.txt"),
    ("", "file"),
    ("...", "file"),
    (".hidden", "file.hidden"),
    ("a/b/c.txt", "c.txt"),
])
def test_safe_object_name(filename, expected):
    assert safe_object_name(filename) == expected


def test_a_very_long_name_is_truncated_but_keeps_its_extension():
    name = safe_object_name("x" * 500 + ".pdf")
    assert len(name) <= 120 and name.endswith(".pdf")


@pytest.mark.parametrize("filename", ["résumé xxxx.txt", "../../etc/passwd.txt", "<script>alert(1)</script>.txt", "ünï©ode_名前.txt", "a\x00b.txt"])
def test_an_uploaded_document_key_is_scoped_to_the_tenant_prefix_and_plain_ascii(fake_s3, filename):
    key = upload_document_file(ORG, DOC, filename, b"x", "text/plain")

    assert key.startswith(f"documents/{ORG}/{DOC}/")
    leaf = key[len(f"documents/{ORG}/{DOC}/"):]
    assert "/" not in leaf and ".." not in leaf and re.fullmatch(r"[A-Za-z0-9._-]+", leaf)
    assert fake_s3.keys == [key]


def test_a_media_key_is_sanitized_the_same_way(fake_s3):
    key = upload_media_file(ORG, DOC, "../vidéo finale.mp4", b"x", "video/mp4")

    assert key == f"media/{ORG}/{DOC}/video_finale.mp4"
