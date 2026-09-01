"""
Audit finding 18 -- writes to and verifies the tamper-evident audit log
(api/models/audit_log.py). Each row's `checksum` is a SHA-256 HMAC over
its own content, chained with the PREVIOUS row's checksum -- altering or
deleting any historical row, or reordering rows, changes what every
checksum computed AFTER it should have been, which verify_audit_log_integrity()
below detects by recomputing the whole chain from AUDIT_LOG_HMAC_SECRET_KEY
(never exposed via any API response).

Concurrency: two audit-log writes committing at the same instant could
otherwise both read the same "previous" checksum and fork the chain
instead of extending it linearly. On Postgres, log_audit_action() takes a
transaction-scoped advisory lock first, serializing writes globally for
the instant it takes to read-then-insert (cheap; audit writes are not a
hot path the way, say, rate-limit checks are). SQLite (the fast test
suite) has no equivalent function -- silently skipped there, which is
fine: SQLite already serializes writers at the database-file level, and
nothing in the test suite issues genuinely concurrent audit writes.
"""

import datetime as dt
import hashlib
import hmac
import json
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.audit_log import AuditAction, AuditLog
from api.utils import as_aware_utc

_CHAIN_LOCK_KEY = 8817  # arbitrary fixed int -- only its uniqueness within this app matters
_GENESIS_CHECKSUM = "genesis"  # the "previous checksum" for the very first row ever written


def _compute_checksum(*, previous_checksum: str, user_id: uuid.UUID | None, action: str, ip: str | None, user_agent: str | None, timestamp: dt.datetime, metadata_json: str | None, success: bool, failure_reason: str | None) -> str:
    payload = "|".join([
        previous_checksum, str(user_id), action, str(ip), str(user_agent),
        timestamp.isoformat(), str(metadata_json), str(success), str(failure_reason),
    ])
    return hmac.new(settings.AUDIT_LOG_HMAC_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


async def log_audit_action(
    db: AsyncSession, *, user_id: uuid.UUID | None, action: AuditAction, ip: str | None, user_agent: str | None,
    success: bool, metadata: dict | None = None, failure_reason: str | None = None,
) -> AuditLog:
    """Writes one row. Caller commits (same convention as every other
    write helper in this codebase, e.g. api/services/password_reset.py) --
    an audit entry is meant to be part of the SAME transaction as the
    action it's recording, so a rolled-back action never leaves behind a
    record of something that didn't actually happen."""
    # Dialect check, not try/except: a failed statement is NOT a safe
    # thing to swallow mid-transaction -- the earlier version of this
    # function caught the DBAPIError SQLite raises for a function it
    # doesn't have and called db.rollback() to "recover," which actually
    # discarded the CALLER's entire pending transaction (e.g. the User
    # row register() had already added, still uncommitted) -- a severe,
    # silent data-loss bug caught by the fast test suite going from 263
    # passing to 109 failing the moment this file was added. Checking
    # the dialect name first means the lock is never even attempted
    # somewhere it can't succeed, so there's nothing to recover from.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _CHAIN_LOCK_KEY})

    previous_checksum = await db.scalar(
        select(AuditLog.checksum).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(1)
    ) or _GENESIS_CHECKSUM

    now = dt.datetime.now(dt.timezone.utc)
    metadata_json = json.dumps(metadata, default=str) if metadata else None
    checksum = _compute_checksum(
        previous_checksum=previous_checksum, user_id=user_id, action=action.value, ip=ip, user_agent=user_agent,
        timestamp=now, metadata_json=metadata_json, success=success, failure_reason=failure_reason,
    )
    row = AuditLog(
        user_id=user_id, action=action.value, ip=ip, user_agent=user_agent, timestamp=now,
        metadata_json=metadata_json, success=success, failure_reason=failure_reason, checksum=checksum,
    )
    db.add(row)
    await db.flush()
    return row


async def verify_audit_log_integrity(db: AsyncSession) -> tuple[bool, uuid.UUID | None]:
    """Recomputes the entire chain from AUDIT_LOG_HMAC_SECRET_KEY and
    compares it against what's actually stored, in insertion order.
    Returns (True, None) if every row's checksum matches what it should
    be given the row before it; (False, <id of the first row that
    doesn't>) the moment a mismatch is found -- that row is either
    altered, or a row before it was altered/deleted/reordered, since
    changing anything upstream changes every checksum downstream too.
    """
    rows = (await db.scalars(select(AuditLog).order_by(AuditLog.timestamp.asc(), AuditLog.id.asc()))).all()
    previous_checksum = _GENESIS_CHECKSUM
    for row in rows:
        expected = _compute_checksum(
            # as_aware_utc: SQLite (tests/conftest.py) round-trips a naive
            # datetime for a value written aware -- .isoformat() on a
            # naive vs. aware datetime produces different strings (no
            # "+00:00" suffix), which would make every checksum
            # miscompare here even with zero tampering. Postgres already
            # round-trips aware, so this is a no-op there.
            previous_checksum=previous_checksum, user_id=row.user_id, action=row.action, ip=row.ip,
            user_agent=row.user_agent, timestamp=as_aware_utc(row.timestamp), metadata_json=row.metadata_json,
            success=row.success, failure_reason=row.failure_reason,
        )
        if expected != row.checksum:
            return False, row.id
        previous_checksum = row.checksum
    return True, None
