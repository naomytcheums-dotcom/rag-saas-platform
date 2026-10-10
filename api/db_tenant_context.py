"""Tenant context for PostgreSQL row level security (Lot A, defence in depth).

The application filters by organization in its own queries; this module also tells PostgreSQL WHICH organization a request acts for,
so that RLS policies (migration 0137 and the following ones, applied table by table) can refuse a query that forgot its filter.

How: `bind_tenant(db, org_id)` remembers the organization on the session and sets the TRANSACTION-LOCAL setting `app.current_org_id`
(`set_config(..., true)`, i.e. SET LOCAL) in the current transaction; an `after_begin` listener re-applies it at the start of every
later transaction of the same session (a commit ends a transaction and its settings). Transaction-local means it can never leak to
another request on a pooled connection, including behind a transaction-mode pooler.

Today the application connects with a role that bypasses RLS (docs/audit, 0098), so this is inert in production until the runtime
role is changed: that switch is an external action, see audit-reports/remediation-2026-10-10/03-tenant-isolation.md. No SQL is
sent on non-PostgreSQL dialects (tests on SQLite are unaffected).
"""

import uuid

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

TENANT_SETTING = "app.current_org_id"
_INFO_KEY = "tenant_org_id"
_SET_SQL = text("SELECT set_config(:name, :value, true)")


@event.listens_for(Session, "after_begin")
def _apply_tenant_to_new_transaction(session, transaction, connection) -> None:
    org_id = session.info.get(_INFO_KEY)
    if org_id and connection.dialect.name == "postgresql":
        connection.execute(_SET_SQL, {"name": TENANT_SETTING, "value": org_id})


async def bind_tenant(db: AsyncSession, org_id: uuid.UUID | str) -> None:
    """Declare the organization this session acts for (call it once the caller's membership is verified)."""
    value = str(org_id)
    db.sync_session.info[_INFO_KEY] = value
    if db.sync_session.get_bind().dialect.name == "postgresql":
        await db.execute(_SET_SQL, {"name": TENANT_SETTING, "value": value})


def clear_tenant(db: AsyncSession) -> None:
    db.sync_session.info.pop(_INFO_KEY, None)
