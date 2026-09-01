"""
Audit finding 23 -- shared data-gathering behind both RGPD export formats
(api/routers/account.py's GET /account/export and /account/export-csv).
One function builds the export dict; each endpoint renders it in its own
format, so JSON and CSV can never quietly drift apart on WHICH fields are
actually included -- a real risk if the CSV path built its own,
separately-maintained query.
"""

import csv
import datetime as dt
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.oauth import OAuthAccount
from api.models.session import Session
from api.models.user import User


async def build_account_export_data(db: AsyncSession, user: User) -> dict:
    """Everything this app knows about `user`, structured -- see
    api/routers/account.py's export_account_data for what's deliberately
    EXCLUDED (password hash, refresh-token hashes, provider access
    tokens) and why."""
    oauth_accounts = await db.scalars(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
    sessions = await db.scalars(select(Session).where(Session.user_id == user.id))

    return {
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "company": user.company,
            "locale": user.locale,
            "timezone": user.timezone,
            "is_email_verified": user.is_email_verified,
            "two_factor_enabled": user.totp_enabled,
            "created_at": user.created_at.isoformat(),
        },
        "consent": {
            "consent_given_at": user.consent_given_at.isoformat() if user.consent_given_at else None,
            "terms_version": user.terms_version,
        },
        "linked_oauth_accounts": [
            {"provider": a.provider.value, "provider_email": a.provider_email, "linked_at": a.created_at.isoformat()}
            for a in oauth_accounts
        ],
        "sessions": [
            {
                "device_info": s.device_info,
                "ip_address": s.ip_address,
                "created_at": s.created_at.isoformat(),
                "last_seen_at": s.last_seen_at.isoformat(),
                "revoked": s.revoked_at is not None,
            }
            for s in sessions
        ],
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def _flatten(value, prefix: str, rows: list[tuple[str, str]]) -> None:
    """Recursively turns the nested export dict into flat (key, value)
    pairs -- CSV is inherently a single flat table, so a list of
    sessions/linked accounts becomes `sessions[0].device_info`,
    `sessions[1].device_info`, etc. rather than needing a second file or
    a zip archive for what's fundamentally still "one export."

    An empty list (e.g. no linked OAuth accounts) still gets its own row
    -- without this, that key would simply never appear anywhere in the
    output, which reads as an incomplete/broken export rather than an
    honest "you have none of these" for a field the JSON export still
    lists explicitly (as `[]`)."""
    if isinstance(value, dict):
        for key, sub_value in value.items():
            _flatten(sub_value, f"{prefix}.{key}" if prefix else key, rows)
    elif isinstance(value, list):
        if not value:
            rows.append((prefix, "(none)"))
        for index, item in enumerate(value):
            _flatten(item, f"{prefix}[{index}]", rows)
    else:
        rows.append((prefix, "" if value is None else str(value)))


def render_account_export_csv(export_data: dict) -> str:
    """Audit finding 23: the same data GET /account/export returns as
    JSON, as a two-column (field, value) CSV instead -- RGPD Art. 20
    requires portability in a "structured, commonly used, machine-
    readable format," and CSV is exactly that for a spreadsheet-oriented
    reader, complementing rather than replacing the JSON export a
    programmatic consumer would actually want."""
    rows: list[tuple[str, str]] = []
    _flatten(export_data, "", rows)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["field", "value"])
    writer.writerows(rows)
    return buffer.getvalue()
