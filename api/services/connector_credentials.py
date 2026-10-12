"""Per-organization credentials for the importers and CRM connectors (docs/DECISIONS.md D17).

Before: every connector read ONE token from the server settings (`JIRA_API_TOKEN`, `ZENDESK_API_TOKEN`...), so a customer could not connect their own account, and an
operator who switched a connector on exposed their own account to every organization.

Now:
  * an organization stores its own credentials (encrypted with ENCRYPTION_MASTER_KEY) with PUT /organizations/{org_id}/connectors/{provider};
  * a connector runs inside `connector_scope(...)`, during which the connector modules (they import `connector_settings as settings`) see ONLY that organization's
    values for the credential fields; a field it did not provide is None, never the server's value;
  * an organization without credentials is refused (403) unless the operator explicitly allowed the legacy shared mode with CONNECTORS_ALLOW_PLATFORM_CREDENTIALS
    (single-tenant installations);
  * host-like fields typed by a customer (a Jira URL, a Zendesk sub-domain...) are validated: https only, a public address, and for vendor-hosted services a host that stays under
    the vendor's domain. The request-time check repeats the address test so a name that later resolves to a private address is refused.

`*_ENABLED` flags keep their meaning: whether the operator offers the connector at all."""

from __future__ import annotations

import asyncio
import contextvars
import ipaddress
import json
import re
import socket
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings as _settings
from api.models.connector_credential import ConnectorCredential
from api.security.encryption import decrypt_data, encrypt_data


@dataclass(frozen=True)
class Field:
    name: str  # the server-setting name the connector module reads
    kind: str  # secret | text | ident (id spliced into a path) | dc (data centre spliced into a host) | url | subdomain
    required: bool = True
    suffixes: tuple[str, ...] = ()  # for url / subdomain: the host must end with one of these (vendor-hosted services)


def _tok(name: str) -> Field:
    return Field(name, "secret")


# provider (the slug used in the routes) -> the credential fields a customer provides
PROVIDERS: dict[str, tuple[Field, ...]] = {
    "salesforce": (Field("SALESFORCE_INSTANCE_URL", "url", suffixes=(".salesforce.com", ".force.com")), Field("SALESFORCE_CLIENT_ID", "text"), _tok("SALESFORCE_CLIENT_SECRET")),
    "hubspot": (_tok("HUBSPOT_API_TOKEN"),),
    "jira": (Field("JIRA_BASE_URL", "url"), Field("JIRA_EMAIL", "text"), _tok("JIRA_API_TOKEN")),
    "zendesk": (Field("ZENDESK_SUBDOMAIN", "subdomain", suffixes=(".zendesk.com",)), Field("ZENDESK_EMAIL", "text"), _tok("ZENDESK_API_TOKEN")),
    "intercom": (_tok("INTERCOM_API_TOKEN"),),
    "shopify": (Field("SHOPIFY_SHOP_DOMAIN", "subdomain", suffixes=(".myshopify.com",)), _tok("SHOPIFY_API_TOKEN")),
    "woocommerce": (Field("WOOCOMMERCE_STORE_URL", "url"), _tok("WOOCOMMERCE_API_TOKEN")),
    "mailchimp": (Field("MAILCHIMP_DC", "dc"), _tok("MAILCHIMP_API_TOKEN")),
    "klaviyo": (_tok("KLAVIYO_API_TOKEN"),),
    "activecampaign": (Field("ACTIVECAMPAIGN_ACCOUNT", "subdomain", suffixes=(".api-us1.com",)), _tok("ACTIVECAMPAIGN_API_TOKEN")),
    "pipedrive": (_tok("PIPEDRIVE_API_TOKEN"),),
    "zoho": (_tok("ZOHO_API_TOKEN"),),
    "docusign": (Field("DOCUSIGN_ACCOUNT_ID", "ident"), _tok("DOCUSIGN_API_TOKEN")),
    "asana": (_tok("ASANA_API_TOKEN"),),
    "trello": (_tok("TRELLO_API_KEY"), _tok("TRELLO_API_TOKEN")),
    "clickup": (_tok("CLICKUP_API_TOKEN"),),
    "monday": (_tok("MONDAY_API_TOKEN"),),
    "linear": (_tok("LINEAR_API_TOKEN"),),
    "airtable": (_tok("AIRTABLE_API_TOKEN"),),
    "coda": (_tok("CODA_API_TOKEN"),),
    "smartsheet": (_tok("SMARTSHEET_API_TOKEN"),),
    "smartsuite": (Field("SMARTSUITE_ACCOUNT_ID", "ident"), _tok("SMARTSUITE_API_TOKEN")),
    "wrike": (_tok("WRIKE_API_TOKEN"),),
    "teamwork": (Field("TEAMWORK_DOMAIN", "subdomain", suffixes=(".teamwork.com",)), _tok("TEAMWORK_API_TOKEN")),
    "basecamp": (_tok("BASECAMP_API_TOKEN"),),
    "hive": (_tok("HIVE_API_TOKEN"),),
    "nifty": (_tok("NIFTY_API_TOKEN"),),
    "podio": (_tok("PODIO_API_TOKEN"),),
    "pipefy": (_tok("PIPEFY_API_TOKEN"),),
    "process_street": (_tok("PROCESS_STREET_API_TOKEN"),),
    "miro": (_tok("MIRO_API_TOKEN"),),
    "gitlab": (_tok("GITLAB_API_TOKEN"),),
    "bitbucket": (_tok("BITBUCKET_API_TOKEN"),),
    "azure_devops": (_tok("AZURE_DEVOPS_API_TOKEN"),),
    "box": (_tok("BOX_API_TOKEN"),),
    "dropbox": (_tok("DROPBOX_API_TOKEN"),),
    "github": (Field("GITHUB_API_TOKEN", "secret", required=False),),  # optional: public repositories need none
    "notion": (_tok("NOTION_API_TOKEN"),),
    "confluence": (Field("CONFLUENCE_BASE_URL", "url"), _tok("CONFLUENCE_API_TOKEN")),
    "google_drive": (Field("GOOGLE_DRIVE_CLIENT_ID", "text"), _tok("GOOGLE_DRIVE_CLIENT_SECRET"), _tok("GOOGLE_DRIVE_REFRESH_TOKEN")),
    "onedrive": (Field("ONEDRIVE_CLIENT_ID", "text"), _tok("ONEDRIVE_CLIENT_SECRET"), _tok("ONEDRIVE_REFRESH_TOKEN")),
}
OPTIONAL_CREDENTIALS = {"github"}  # may run without credentials (public data only)
# google-docs shares the Drive credentials
ALIASES = {"google_docs": "google_drive", "google-drive": "google_drive", "google-docs": "google_drive", "azure-devops": "azure_devops", "process-street": "process_street"}

_FIELD_TO_PROVIDER = {field.name: provider for provider, fields in PROVIDERS.items() for field in fields}
_CREDENTIAL_NAMES = frozenset(_FIELD_TO_PROVIDER)

_active: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar("connector_credentials", default=None)
_SUBDOMAIN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_IDENT = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_DC = re.compile(r"^[a-z]{2}\d{1,2}$")
_LIMIT = 2048


def normalize_provider(provider: str) -> str:
    provider = ALIASES.get(provider, provider)
    if provider not in PROVIDERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown connector '{provider}'")
    return provider


class _SettingsProxy:
    """Stands in for `settings` inside the connector modules: credential fields come from the active organization, everything else from the real settings."""

    def __getattr__(self, name: str) -> Any:
        active = _active.get()
        if active is not None and name in _CREDENTIAL_NAMES:
            return active.get(name)  # never the server's value while an organization's scope is active
        return getattr(_settings, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(_settings, name, value)

    def __delattr__(self, name: str) -> None:
        delattr(_settings, name)


connector_settings = _SettingsProxy()


# ------------------------------------------------------------------ validation


def _public_host_or_raise(host: str) -> None:
    """The host must resolve only to public addresses (checked at save time and again at use time)."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"the host '{host}' does not resolve") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError(f"the host '{host}' does not resolve to a public address")


def validate_value(field: Field, value: str, *, resolve: bool = True) -> str:
    value = (value or "").strip()
    if not value or len(value) > _LIMIT:
        raise ValueError(f"{field.name} must be 1 to {_LIMIT} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field.name} must not contain control characters")
    if field.kind == "ident" and not _IDENT.match(value):
        raise ValueError(f"{field.name} may only contain letters, digits, dot, underscore and hyphen")
    if field.kind == "dc" and not _DC.match(value):
        raise ValueError(f"{field.name} must look like 'us21'")
    if field.kind == "subdomain":
        label = value.lower()
        suffix = field.suffixes[0] if field.suffixes else ""
        if label.endswith(suffix):  # the customer may paste the full host
            label = label[: -len(suffix)]
        if not _SUBDOMAIN.match(label):
            raise ValueError(f"{field.name} must be a single sub-domain (letters, digits, hyphen), not an address")
        if resolve:
            _public_host_or_raise(label + suffix)
        return label if field.name in {"ZENDESK_SUBDOMAIN", "TEAMWORK_DOMAIN", "ACTIVECAMPAIGN_ACCOUNT"} else label + suffix
    if field.kind == "url":
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
            raise ValueError(f"{field.name} must be an https address without credentials or custom port")
        host = parts.hostname.lower()
        if field.suffixes and not any(host == s.lstrip(".") or host.endswith(s) for s in field.suffixes):
            raise ValueError(f"{field.name} must be a host under {', '.join(field.suffixes)}")
        if resolve:
            _public_host_or_raise(host)
        return f"https://{host}{parts.path.rstrip('/')}"
    return value


def validate_credentials(provider: str, values: dict[str, str], *, resolve: bool = True) -> dict[str, str]:
    fields = {f.name: f for f in PROVIDERS[provider]}
    unknown = sorted(set(values) - set(fields))
    if unknown:
        raise ValueError(f"unknown fields {unknown}; expected {sorted(fields)}")
    missing = sorted(name for name, f in fields.items() if f.required and not (values.get(name) or "").strip())
    if missing:
        raise ValueError(f"missing fields {missing}")
    return {name: validate_value(fields[name], value, resolve=resolve) for name, value in values.items() if (value or "").strip()}


# ------------------------------------------------------------------ storage


async def load_credentials(db: AsyncSession, organization_id: uuid.UUID, provider: str) -> dict[str, str] | None:
    row = await db.scalar(select(ConnectorCredential).where(ConnectorCredential.organization_id == organization_id, ConnectorCredential.provider == provider))
    if row is None:
        return None
    return json.loads(decrypt_data(row.encrypted_payload))


async def save_credentials(db: AsyncSession, organization_id: uuid.UUID, provider: str, values: dict[str, str], user_id: uuid.UUID | None) -> ConnectorCredential:
    payload = encrypt_data(json.dumps(values))
    row = await db.scalar(select(ConnectorCredential).where(ConnectorCredential.organization_id == organization_id, ConnectorCredential.provider == provider))
    if row is None:
        row = ConnectorCredential(organization_id=organization_id, provider=provider, encrypted_payload=payload, created_by=user_id)
        db.add(row)
    else:
        row.encrypted_payload = payload
    await db.flush()
    return row


async def delete_credentials(db: AsyncSession, organization_id: uuid.UUID, provider: str) -> bool:
    row = await db.scalar(select(ConnectorCredential).where(ConnectorCredential.organization_id == organization_id, ConnectorCredential.provider == provider))
    if row is None:
        return False
    await db.delete(row)
    await db.flush()
    return True


async def connected_providers(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, ConnectorCredential]:
    rows = (await db.scalars(select(ConnectorCredential).where(ConnectorCredential.organization_id == organization_id))).all()
    return {row.provider: row for row in rows}


# ------------------------------------------------------------------ scope

_PLATFORM = "platform"
_PUBLIC = "public"


def _recheck_hosts(provider: str, values: dict[str, str]) -> None:
    """Request-time repeat of the address test for host-like fields."""
    for field in PROVIDERS[provider]:
        if field.kind in {"url", "subdomain"} and values.get(field.name):
            host = urlsplit(values[field.name]).hostname if field.kind == "url" else (values[field.name] + (field.suffixes[0] if field.suffixes else ""))
            _public_host_or_raise(host)


async def _resolve(db: AsyncSession, organization_id: uuid.UUID, provider: str) -> tuple[str, Any]:
    """The credentials a run for this organization may use: its own, the server's (only if the operator allowed the shared mode), none (public data), or a 403."""
    provider = normalize_provider(provider)
    stored = await load_credentials(db, organization_id, provider)
    if stored is not None:
        try:
            await asyncio.to_thread(_recheck_hosts, provider, stored)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Stored {provider} credentials are not usable: {exc}") from exc
        return provider, stored
    if _settings.CONNECTORS_ALLOW_PLATFORM_CREDENTIALS:
        return provider, _PLATFORM
    if provider in OPTIONAL_CREDENTIALS:
        return provider, _PUBLIC
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"This organization has not connected {provider}. Add its credentials first (PUT /organizations/{{org_id}}/connectors/{provider}).",
    )


@asynccontextmanager
async def _activated(resolved: tuple[str, Any]) -> AsyncIterator[None]:
    _provider, mode = resolved
    token = _active.set(None if mode == _PLATFORM else ({} if mode == _PUBLIC else mode))
    try:
        yield
    finally:
        _active.reset(token)


@asynccontextmanager
async def connector_scope_for(db: AsyncSession, organization_id: uuid.UUID, provider: str) -> AsyncIterator[None]:
    async with _activated(await _resolve(db, organization_id, provider)):
        yield


def connector_scope(provider: str) -> Callable[..., AsyncIterator[None]]:
    """FastAPI dependency (add to a route): the route body runs inside the organization's scope."""
    from api.database import get_db

    async def _dependency(org_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> AsyncIterator[None]:
        async with connector_scope_for(db, org_id, provider):
            yield

    return _dependency


async def run_in_scope(provider: str, organization_id: str | uuid.UUID, coroutine_factory: Callable[[], Awaitable[Any]]) -> Any:
    """For background tasks (they run in their own event loop with their own engine): resolve the credentials, then run the coroutine inside the scope."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from api.tasks._db import make_async_engine

    engine = make_async_engine()
    try:
        async with async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)() as db:
            resolved = await _resolve(db, uuid.UUID(str(organization_id)), provider)
    finally:
        await engine.dispose()
    async with _activated(resolved):
        return await coroutine_factory()
