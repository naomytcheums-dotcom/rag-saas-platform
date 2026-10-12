"""Audit item 10.1.12 (malware scanning): the scan against a REAL clamd, opt-in.

tests/test_clamav.py checks the wire protocol with a fake daemon. This file talks to a real ClamAV daemon and uses the EICAR test string, the
standard harmless file every antivirus detects. Skipped unless CLAMAV_REAL_TEST_HOST is set, for example after

    docker run -d --name rag-test-clamav -p 127.0.0.1:3310:3310 clamav/clamav:stable        (wait until `clamdscan --ping` answers)
    CLAMAV_REAL_TEST_HOST=127.0.0.1 pytest tests/test_clamav_real_daemon.py

The EICAR string is assembled at run time so that this source file is not itself quarantined by an antivirus on a developer machine."""

import os

import pytest

from api.config import settings
from api.services.clamav import ClamAVScanError, scan_document_for_malware

HOST = os.environ.get("CLAMAV_REAL_TEST_HOST", "")
PORT = int(os.environ.get("CLAMAV_REAL_TEST_PORT", "3310"))

pytestmark = pytest.mark.skipif(not HOST, reason="CLAMAV_REAL_TEST_HOST is not set (no real clamd to talk to)")

EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!" + "$H+H*").encode()


@pytest.fixture(autouse=True)
def _real_scanner(monkeypatch):
    monkeypatch.setattr(settings, "CLAMAV_ENABLED", True)
    monkeypatch.setattr(settings, "CLAMAV_SOCKET_PATH", None)
    monkeypatch.setattr(settings, "CLAMAV_HOST", HOST)
    monkeypatch.setattr(settings, "CLAMAV_PORT", PORT)
    monkeypatch.setattr(settings, "CLAMAV_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(settings, "CLAMAV_REQUIRED", True)


def test_the_eicar_test_file_is_rejected_as_malware():
    with pytest.raises(ValueError, match="malware detected"):
        scan_document_for_malware("invoice.pdf", EICAR)


def test_a_clean_document_passes():
    scan_document_for_malware("notes.txt", b"Quarterly notes: nothing unusual here.\n" * 200)


def test_a_large_clean_document_is_streamed_in_chunks():
    scan_document_for_malware("big.bin", b"A" * (3 * 1024 * 1024))


def test_the_eicar_file_with_the_trailing_line_ending_the_standard_allows_is_found():
    # The EICAR signature matches the whole file (the standard allows trailing whitespace), not the string buried in a larger file:
    # that is how the test signature works, not a gap of the scan.
    with pytest.raises(ValueError, match="malware detected"):
        scan_document_for_malware("invoice.pdf", EICAR + b"\r\n")


def test_an_unreachable_scanner_fails_closed_when_the_scan_is_required(monkeypatch):
    monkeypatch.setattr(settings, "CLAMAV_PORT", 1)
    with pytest.raises(ClamAVScanError):
        scan_document_for_malware("notes.txt", b"anything")


def test_an_unreachable_scanner_lets_the_upload_through_when_the_scan_is_optional(monkeypatch):
    monkeypatch.setattr(settings, "CLAMAV_PORT", 1)
    monkeypatch.setattr(settings, "CLAMAV_REQUIRED", False)
    scan_document_for_malware("notes.txt", b"anything")


def test_infected_is_rejected_even_when_the_scan_is_optional(monkeypatch):
    monkeypatch.setattr(settings, "CLAMAV_REQUIRED", False)
    with pytest.raises(ValueError, match="malware detected"):
        scan_document_for_malware("invoice.pdf", EICAR)


async def test_an_upload_through_the_api_is_refused_when_the_file_is_the_eicar_test_file(client, db_session, register_payload, monkeypatch):
    """End to end: the document upload endpoint, with the real scanner switched on, refuses the EICAR file and accepts a clean one."""
    from test_documents import _create_org, _register, _stub_s3, _upload

    _stub_s3(monkeypatch)
    token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, token, "Scanned Org")

    infected = await _upload(client, org["id"], token, filename="invoice.txt", content=EICAR, declared_content_type="text/plain")
    assert infected.status_code == 400, infected.text
    assert "malware" in infected.text.lower()

    clean = await _upload(client, org["id"], token, filename="notes.txt", content=b"Plain notes about the project.\n", declared_content_type="text/plain")
    assert clean.status_code == 201, clean.text
