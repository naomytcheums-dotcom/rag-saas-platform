"""Optional ClamAV scan of an uploaded document, through clamd's INSTREAM command (disabled by default: CLAMAV_ENABLED).

Two different failures, two different policies:
- a file clamd reports as infected is ALWAYS rejected, whatever CLAMAV_REQUIRED says;
- the scanner being unreachable or answering with an error is rejected only when CLAMAV_REQUIRED is true (fail closed); otherwise the
  upload goes through and the problem is logged.

Wire protocol (clamd, "z" = NUL-terminated commands and replies): send `zINSTREAM\\0`, then the data as chunks, each prefixed by its
length as a 4-byte BIG-endian integer, then a zero-length chunk; clamd answers `stream: OK`, `stream: <signature> FOUND` or `<text> ERROR`.
"""

import asyncio
import logging
import socket
import struct

from api.config import settings

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024


class ClamAVScanError(ValueError):
    """The scanner could not give a verdict (a ValueError so that the upload endpoints answer 4xx, never 500)."""


def _connect_clamd() -> socket.socket:
    timeout = settings.CLAMAV_TIMEOUT_SECONDS
    if settings.CLAMAV_SOCKET_PATH and hasattr(socket, "AF_UNIX"):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(settings.CLAMAV_SOCKET_PATH)
        return sock
    if settings.CLAMAV_HOST:
        return socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout)
    raise OSError("ClamAV is enabled but no usable socket path or host/port is configured")


def _send_instream(sock: socket.socket, content: bytes) -> None:
    sock.sendall(b"zINSTREAM\0")
    for start in range(0, len(content), _CHUNK_SIZE):
        chunk = content[start:start + _CHUNK_SIZE]
        sock.sendall(struct.pack(">I", len(chunk)) + chunk)
    sock.sendall(struct.pack(">I", 0))


def _read_reply(sock: socket.socket) -> str:
    received = bytearray()
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        received.extend(chunk)
        if b"\0" in chunk or b"\n" in chunk:
            break
    return received.decode("utf-8", errors="replace").replace("\0", "").strip()


def scan_document_for_malware(filename: str, content: bytes) -> None:
    """Synchronous scan. Raises ValueError for an infected file, ClamAVScanError when a required scan gives no verdict."""
    if not content:
        return
    try:
        with _connect_clamd() as sock:
            _send_instream(sock, content)
            reply = _read_reply(sock)
    except OSError as exc:  # includes timeouts and refused connections
        return _no_verdict(filename, f"scanner unreachable ({type(exc).__name__})")

    if reply.endswith("FOUND"):
        signature = reply.removeprefix("stream:").removesuffix("FOUND").strip() or "unknown signature"
        logger.warning("Malware detected in '%s': %s", filename, signature)
        raise ValueError(f"Upload rejected: malware detected in '{filename}' ({signature})")
    if reply.endswith("OK"):
        return
    return _no_verdict(filename, f"unexpected scanner reply {reply[:120]!r}")


def _no_verdict(filename: str, reason: str) -> None:
    if settings.CLAMAV_REQUIRED:
        logger.error("ClamAV gave no verdict for '%s' (%s); upload refused because CLAMAV_REQUIRED is true", filename, reason)
        raise ClamAVScanError(f"The malware scan of '{filename}' could not be completed; the upload was refused")
    logger.warning("ClamAV gave no verdict for '%s' (%s); continuing because CLAMAV_REQUIRED is false", filename, reason)


async def ascan_document_for_malware(filename: str, content: bytes) -> None:
    """The scan on a worker thread: a slow or dead scanner must never stall the event loop that serves every other request."""
    await asyncio.to_thread(scan_document_for_malware, filename, content)
