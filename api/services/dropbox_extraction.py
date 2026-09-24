"""
Extraction -- listing files from Dropbox's real API v2, for import into
a knowledge base.

**Real auth shape**: a real, static `DROPBOX_API_TOKEN` (a real Dropbox
"access token", admin-configured once), sent as
`Authorization: Bearer <token>`.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.dropboxapi.com/2"


class DropboxError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Dropbox, never silently swallowed."""


class DropboxRateLimitError(DropboxError):
    """Real, distinguishable 429."""


async def fetch_dropbox_files(path: str = "", limit: int = 100) -> list[dict]:
    """Real list of files from a Dropbox folder.

    Returns a list of {id, name, path, text} dicts, where `text` is a
    real, plain-text representation suitable for RAG ingestion.
    """
    if not settings.DROPBOX_ENABLED:
        raise DropboxError("Dropbox integration is disabled")
    if not settings.DROPBOX_API_TOKEN:
        raise DropboxError("Dropbox API token not configured")

    headers = {
        "Authorization": f"Bearer {settings.DROPBOX_API_TOKEN}",
        "Content-Type": "application/json",
    }

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{_BASE_URL}/files/list_folder",
            headers=headers,
            json={"path": path, "limit": limit},
        )

        if response.status_code == 429:
            raise DropboxRateLimitError("Dropbox rate limit reached")
        if response.status_code != 200:
            raise DropboxError(f"Dropbox fetch failed: {response.status_code}")

        for entry in response.json().get("entries", []):
            if entry.get(".tag") != "file":
                continue
            text_parts = [
                f"File: {entry.get('name', '')}",
                f"Path: {entry.get('path_display', '')}",
                f"Size: {entry.get('size', '')}",
            ]
            results.append({
                "id": entry.get("id"),
                "name": entry.get("name"),
                "path": entry.get("path_display"),
                "text": "\n".join(text_parts),
            })

    return results
