"""The ClamAV scan against a fake clamd that speaks the REAL INSTREAM wire protocol (NUL-terminated command, big-endian chunk lengths,
zero-length terminator, `stream: OK` / `stream: <sig> FOUND` replies), so a framing or parsing mistake fails here and not in production."""

import asyncio
import socket
import struct
import threading
import time

import pytest

from api.config import settings
from api.services.clamav import ClamAVScanError, ascan_document_for_malware, scan_document_for_malware

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def _recv_exact(conn, size):
    data = b""
    while len(data) < size:
        piece = conn.recv(size - len(data))
        if not piece:
            raise ConnectionError("client closed early")
        data += piece
    return data


class FakeClamd:
    """One-shot clamd. `reply` is None to compute it from the payload (EICAR -> FOUND), or a fixed bytes reply. `delay` stalls the answer."""

    def __init__(self, reply=None, delay=0.0):
        self.received = None
        self.errors = []
        self._reply, self._delay = reply, delay
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(1)
        self.port = self._server.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        try:
            conn, _ = self._server.accept()
            with conn:
                command = _recv_exact(conn, len(b"zINSTREAM\0"))
                if command != b"zINSTREAM\0":
                    self.errors.append(f"bad command {command!r}")
                payload = b""
                while True:
                    (length,) = struct.unpack(">I", _recv_exact(conn, 4))  # big-endian: the protocol's network byte order
                    if length == 0:
                        break
                    payload += _recv_exact(conn, length)
                self.received = payload
                time.sleep(self._delay)
                reply = self._reply if self._reply is not None else (b"stream: Eicar-Test-Signature FOUND\0" if EICAR in payload else b"stream: OK\0")
                conn.sendall(reply)
        except Exception as exc:  # noqa: BLE001 -- surfaced through the test assertion on .errors
            self.errors.append(repr(exc))
        finally:
            self._server.close()

    def join(self):
        self._thread.join(timeout=5)


@pytest.fixture
def configure(monkeypatch):
    def _configure(port, *, required=False):
        monkeypatch.setattr(settings, "CLAMAV_SOCKET_PATH", None)
        monkeypatch.setattr(settings, "CLAMAV_HOST", "127.0.0.1")
        monkeypatch.setattr(settings, "CLAMAV_PORT", port)
        monkeypatch.setattr(settings, "CLAMAV_REQUIRED", required)
        monkeypatch.setattr(settings, "CLAMAV_TIMEOUT_SECONDS", 5)

    return _configure


def test_a_clean_file_passes_and_arrives_intact_across_several_chunks(configure):
    payload = bytes(range(256)) * 1000  # 256 000 bytes: four chunks of at most 64 KiB
    clamd = FakeClamd()
    configure(clamd.port, required=True)
    scan_document_for_malware("clean.bin", payload)
    clamd.join()
    assert clamd.errors == []
    assert clamd.received == payload


@pytest.mark.parametrize("required", [True, False])
def test_an_infected_file_is_rejected_whatever_required_says(configure, required):
    clamd = FakeClamd()
    configure(clamd.port, required=required)
    with pytest.raises(ValueError, match="malware detected"):
        scan_document_for_malware("infected.txt", EICAR)
    clamd.join()
    assert clamd.errors == []


def test_an_unreachable_scanner_lets_the_upload_through_when_not_required(configure):
    configure(65535, required=False)
    scan_document_for_malware("no-scanner.txt", b"content")


def test_an_unreachable_scanner_refuses_the_upload_when_required(configure):
    configure(65535, required=True)
    with pytest.raises(ClamAVScanError, match="could not be completed"):
        scan_document_for_malware("no-scanner.txt", b"content")


def test_a_scanner_error_reply_is_refused_only_when_required(configure):
    clamd = FakeClamd(reply=b"INSTREAM size limit exceeded. ERROR\0")
    configure(clamd.port, required=True)
    with pytest.raises(ClamAVScanError):
        scan_document_for_malware("big.bin", b"content")
    clamd.join()

    clamd = FakeClamd(reply=b"INSTREAM size limit exceeded. ERROR\0")
    configure(clamd.port, required=False)
    scan_document_for_malware("big.bin", b"content")
    clamd.join()


def test_an_empty_file_is_not_sent_to_the_scanner(configure):
    configure(65535, required=True)
    scan_document_for_malware("empty.txt", b"")  # would raise if it tried to connect


async def test_a_slow_scanner_does_not_stall_the_event_loop(configure):
    clamd = FakeClamd(delay=0.6)
    configure(clamd.port)
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.05)
            ticks += 1

    task = asyncio.create_task(ticker())
    await ascan_document_for_malware("slow.txt", b"content")
    task.cancel()
    clamd.join()
    assert ticks >= 6, f"the event loop only ticked {ticks} times during a 0.6 s scan: the scan blocks it"
