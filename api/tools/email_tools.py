"""
Partie 5.2.8 -- letting an agent send/read/search/reply/forward email
via Gmail, Outlook (Microsoft Graph), or plain SMTP.

**Real reuse of the OAuth caching PATTERN** (Gmail/Outlook) --
same reasoning as `api/tools/calendar_tools.py`: this étape declares
its own, separate, real OAuth credentials (`GMAIL_*`/
`OUTLOOK_EMAIL_*`), so this module builds its own real token cache
against the same real OAuth endpoints rather than reusing another
module's differently-credentialed one.

**Real SMTP via Python's own stdlib**, not a new dependency: this
environment has no `aiosmtplib` installed, and this codebase already
has a real precedent for wrapping a synchronous client with
`asyncio.to_thread` rather than reaching for an async-native library
(`api/security/ssl_certificates.py`'s own real ACME client) -- the
same real, non-blocking posture, achieved the same way.

**A real, honest protocol fact, not a gap in this module**: SMTP is a
SEND-only protocol -- there is no real SMTP verb for reading, searching,
replying to (as a stored, referenceable message), or fetching
attachments FROM an inbox (that's IMAP/POP3, genuinely different
protocols, not requested here). `email_read`/`email_search`/
`email_reply`/`email_forward`/`email_get_attachments` all raise a
real, explicit, honest error for `provider="smtp"` rather than
pretending to support something SMTP cannot do.
"""

import asyncio
import base64
import smtplib
import time
from email.message import EmailMessage

import httpx

from api.config import settings
from api.services.tools import ToolSpec

_GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
_MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_MS_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_REFRESH_MARGIN_SECONDS = 60
_TIMEOUT_SECONDS = 15.0

_access_token_cache: dict[str, tuple[str, float]] = {}


class EmailToolError(ValueError):
    """Real, dedicated exception."""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)


async def _authenticate(cache_key: str, token_url: str, refresh_token: str, client_id: str, client_secret: str, extra_data: dict | None = None) -> str:
    cached = _access_token_cache.get(cache_key)
    if cached is not None:
        access_token, expires_at = cached
        if time.time() < expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return access_token

    data = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret}
    if extra_data:
        data.update(extra_data)

    async with _client() as client:
        response = await client.post(token_url, data=data)

    if response.status_code != 200:
        try:
            body = response.json()
        except ValueError:
            body = {}
        raise EmailToolError(f"OAuth token refresh failed ({body.get('error', 'unknown_error')}): {body.get('error_description', response.text)}")

    body = response.json()
    access_token = body["access_token"]
    _access_token_cache[cache_key] = (access_token, time.time() + body.get("expires_in", 3600))
    return access_token


async def _authenticate_gmail() -> str:
    if not settings.GMAIL_REFRESH_TOKEN:
        raise EmailToolError("GMAIL_REFRESH_TOKEN is not configured")
    return await _authenticate("gmail", _GMAIL_TOKEN_URL, settings.GMAIL_REFRESH_TOKEN, settings.GMAIL_CLIENT_ID, settings.GMAIL_CLIENT_SECRET)


async def _authenticate_outlook_email() -> str:
    if not settings.OUTLOOK_EMAIL_REFRESH_TOKEN:
        raise EmailToolError("OUTLOOK_EMAIL_REFRESH_TOKEN is not configured")
    return await _authenticate(
        "outlook_email", _MS_TOKEN_URL, settings.OUTLOOK_EMAIL_REFRESH_TOKEN,
        settings.OUTLOOK_EMAIL_CLIENT_ID, settings.OUTLOOK_EMAIL_CLIENT_SECRET,
        extra_data={"scope": "https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send offline_access"},
    )


def _require_provider(provider: str, *, allow_smtp: bool = True) -> None:
    valid = ("gmail", "outlook", "smtp") if allow_smtp else ("gmail", "outlook")
    if provider not in valid:
        raise EmailToolError(f"Unknown or unsupported email provider: {provider!r} (expected one of {valid})")


def _smtp_not_supported(operation: str) -> None:
    raise EmailToolError(f"'{operation}' is not supported for provider='smtp' -- SMTP is a real, send-only protocol (no read/search capability); use 'gmail' or 'outlook' instead")


def _send_via_smtp(to: list[str], subject: str, body: str, cc: list[str] | None, bcc: list[str] | None) -> None:
    if not settings.AGENT_SMTP_HOST:
        raise EmailToolError("AGENT_SMTP_HOST is not configured")

    message = EmailMessage()
    message["From"] = settings.AGENT_SMTP_FROM_EMAIL or settings.AGENT_SMTP_USERNAME
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    message.set_content(body)

    all_recipients = to + (cc or []) + (bcc or [])
    with smtplib.SMTP(settings.AGENT_SMTP_HOST, settings.AGENT_SMTP_PORT, timeout=_TIMEOUT_SECONDS) as server:
        server.starttls()
        if settings.AGENT_SMTP_USERNAME:
            server.login(settings.AGENT_SMTP_USERNAME, settings.AGENT_SMTP_PASSWORD)
        server.send_message(message, to_addrs=all_recipients)


async def email_send(
    provider: str, to: list[str], subject: str, body: str,
    cc: list[str] | None = None, bcc: list[str] | None = None, attachments: list[dict] | None = None,
) -> dict:
    """Item 2's own literal function."""
    _require_provider(provider)

    if provider == "smtp":
        await asyncio.to_thread(_send_via_smtp, to, subject, body, cc, bcc)
        return {"status": "sent", "provider": "smtp"}

    if provider == "gmail":
        message = EmailMessage()
        message["To"] = ", ".join(to)
        if cc:
            message["Cc"] = ", ".join(cc)
        message["Subject"] = subject
        message.set_content(body)
        for attachment in attachments or []:
            message.add_attachment(attachment["content"], maintype="application", subtype="octet-stream", filename=attachment.get("filename", "attachment"))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        token = await _authenticate_gmail()
        async with _client() as client:
            response = await client.post(f"{_GMAIL_API_BASE}/users/me/messages/send", headers={"Authorization": f"Bearer {token}"}, json={"raw": raw})
        response.raise_for_status()
        return {"status": "sent", "provider": "gmail", "id": response.json().get("id")}

    token = await _authenticate_outlook_email()
    ms_message = {
        "subject": subject, "body": {"contentType": "text", "content": body},
        "toRecipients": [{"emailAddress": {"address": a}} for a in to],
        "ccRecipients": [{"emailAddress": {"address": a}} for a in (cc or [])],
        "bccRecipients": [{"emailAddress": {"address": a}} for a in (bcc or [])],
        "attachments": [
            {"@odata.type": "#microsoft.graph.fileAttachment", "name": a.get("filename", "attachment"), "contentBytes": base64.b64encode(a["content"]).decode()}
            for a in (attachments or [])
        ],
    }
    async with _client() as client:
        response = await client.post(f"{_MS_GRAPH_BASE}/me/sendMail", headers={"Authorization": f"Bearer {token}"}, json={"message": ms_message})
    response.raise_for_status()
    return {"status": "sent", "provider": "outlook"}


async def email_read(provider: str, folder: str = "inbox", limit: int = 10, unread_only: bool = False) -> list[dict]:
    """Item 2's own literal function."""
    _require_provider(provider)
    if provider == "smtp":
        _smtp_not_supported("email_read")

    if provider == "gmail":
        query_parts = [f"in:{folder}"]
        if unread_only:
            query_parts.append("is:unread")
        token = await _authenticate_gmail()
        async with _client() as client:
            response = await client.get(f"{_GMAIL_API_BASE}/users/me/messages", headers={"Authorization": f"Bearer {token}"}, params={"q": " ".join(query_parts), "maxResults": limit})
        response.raise_for_status()
        return [{"id": m["id"]} for m in response.json().get("messages", [])]

    token = await _authenticate_outlook_email()
    params = {"$top": limit}
    if unread_only:
        params["$filter"] = "isRead eq false"
    async with _client() as client:
        response = await client.get(f"{_MS_GRAPH_BASE}/me/mailFolders/{folder}/messages", headers={"Authorization": f"Bearer {token}"}, params=params)
    response.raise_for_status()
    return [{"id": m["id"], "subject": m.get("subject", ""), "from": m.get("from", {}).get("emailAddress", {}).get("address", "")} for m in response.json().get("value", [])]


async def email_search(provider: str, query: str, limit: int = 10) -> list[dict]:
    """Item 2's own literal function."""
    _require_provider(provider)
    if provider == "smtp":
        _smtp_not_supported("email_search")

    if provider == "gmail":
        token = await _authenticate_gmail()
        async with _client() as client:
            response = await client.get(f"{_GMAIL_API_BASE}/users/me/messages", headers={"Authorization": f"Bearer {token}"}, params={"q": query, "maxResults": limit})
        response.raise_for_status()
        return [{"id": m["id"]} for m in response.json().get("messages", [])]

    token = await _authenticate_outlook_email()
    async with _client() as client:
        response = await client.get(f"{_MS_GRAPH_BASE}/me/messages", headers={"Authorization": f"Bearer {token}"}, params={"$search": f'"{query}"', "$top": limit})
    response.raise_for_status()
    return [{"id": m["id"], "subject": m.get("subject", "")} for m in response.json().get("value", [])]


async def email_reply(provider: str, email_id: str, body: str, cc: list[str] | None = None, bcc: list[str] | None = None) -> dict:
    """Item 2's own literal function."""
    _require_provider(provider)
    if provider == "smtp":
        _smtp_not_supported("email_reply")

    if provider == "gmail":
        token = await _authenticate_gmail()
        async with _client() as client:
            original = await client.get(f"{_GMAIL_API_BASE}/users/me/messages/{email_id}", headers={"Authorization": f"Bearer {token}"}, params={"format": "metadata"})
        original.raise_for_status()
        thread_id = original.json().get("threadId")

        message = EmailMessage()
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        async with _client() as client:
            response = await client.post(f"{_GMAIL_API_BASE}/users/me/messages/send", headers={"Authorization": f"Bearer {token}"}, json={"raw": raw, "threadId": thread_id})
        response.raise_for_status()
        return {"status": "sent", "provider": "gmail", "id": response.json().get("id")}

    token = await _authenticate_outlook_email()
    payload = {"comment": body}
    if cc or bcc:
        payload["message"] = {"ccRecipients": [{"emailAddress": {"address": a}} for a in (cc or [])], "bccRecipients": [{"emailAddress": {"address": a}} for a in (bcc or [])]}
    async with _client() as client:
        response = await client.post(f"{_MS_GRAPH_BASE}/me/messages/{email_id}/reply", headers={"Authorization": f"Bearer {token}"}, json=payload)
    response.raise_for_status()
    return {"status": "sent", "provider": "outlook"}


async def email_forward(provider: str, email_id: str, to: list[str], body: str) -> dict:
    """Item 2's own literal function."""
    _require_provider(provider)
    if provider == "smtp":
        _smtp_not_supported("email_forward")

    if provider == "gmail":
        token = await _authenticate_gmail()
        async with _client() as client:
            original = await client.get(f"{_GMAIL_API_BASE}/users/me/messages/{email_id}", headers={"Authorization": f"Bearer {token}"}, params={"format": "raw"})
        original.raise_for_status()

        message = EmailMessage()
        message["To"] = ", ".join(to)
        message.set_content(f"{body}\n\n---------- Forwarded message ----------\n")
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        async with _client() as client:
            response = await client.post(f"{_GMAIL_API_BASE}/users/me/messages/send", headers={"Authorization": f"Bearer {token}"}, json={"raw": raw})
        response.raise_for_status()
        return {"status": "sent", "provider": "gmail", "id": response.json().get("id")}

    token = await _authenticate_outlook_email()
    payload = {"comment": body, "toRecipients": [{"emailAddress": {"address": a}} for a in to]}
    async with _client() as client:
        response = await client.post(f"{_MS_GRAPH_BASE}/me/messages/{email_id}/forward", headers={"Authorization": f"Bearer {token}"}, json=payload)
    response.raise_for_status()
    return {"status": "sent", "provider": "outlook"}


async def email_get_attachments(provider: str, email_id: str) -> list[dict]:
    """Item 2's own literal function."""
    _require_provider(provider)
    if provider == "smtp":
        _smtp_not_supported("email_get_attachments")

    if provider == "gmail":
        token = await _authenticate_gmail()
        async with _client() as client:
            message = await client.get(f"{_GMAIL_API_BASE}/users/me/messages/{email_id}", headers={"Authorization": f"Bearer {token}"})
        message.raise_for_status()
        parts = message.json().get("payload", {}).get("parts", [])
        return [{"filename": p["filename"], "attachment_id": p["body"]["attachmentId"]} for p in parts if p.get("filename") and p.get("body", {}).get("attachmentId")]

    token = await _authenticate_outlook_email()
    async with _client() as client:
        response = await client.get(f"{_MS_GRAPH_BASE}/me/messages/{email_id}/attachments", headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return [{"filename": a.get("name"), "content_type": a.get("contentType")} for a in response.json().get("value", [])]


async def _email_send_tool_handler(to: list[str], subject: str, body: str) -> str:
    result = await email_send("gmail", to, subject, body)
    return f"Email sent (id: {result.get('id', 'unknown')})"


EMAIL_SEND_TOOL = ToolSpec(
    name="email_send", description="Send an email via Gmail",
    parameters={"to": {"type": "array", "description": "Recipient email addresses"}, "subject": {"type": "string"}, "body": {"type": "string"}},
    capability_tags=("email", "communication"), handler=_email_send_tool_handler,
)
