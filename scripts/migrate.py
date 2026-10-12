"""Apply the pending Alembic migrations safely (spec 13.3.8): rehearse first, apply only when asked.

    python scripts/migrate.py            # rehearsal only: the pending migrations run inside ONE transaction that is ALWAYS rolled back
    python scripts/migrate.py --apply    # the rehearsal, then (only if it passed) `alembic upgrade head` for real

The database comes from DATABASE_URL (environment). Nothing is committed unless `--apply` is given AND the rehearsal passed. The rehearsal generates
the SQL of every pending migration offline (`alembic upgrade <current>:head --sql`) and runs it against the real server (PostgreSQL has transactional
DDL), so a migration that would fail is caught before it touches anything. A migration that cannot run inside a transaction (for example
CREATE INDEX CONCURRENTLY) makes the rehearsal fail with a clear message: apply it by hand in that case. No credential is ever printed.
Take a backup first (scripts/backup.sh). Superseded one-off tool: scripts/migrate_with_rehearsal.py (written for migration 0133 only).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

import asyncpg
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parent.parent
TRANSACTION_MARKERS = {"BEGIN;", "COMMIT;"}


def head_revision() -> str:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "api" / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    return re.sub(r"^postgresql\+asyncpg", "postgresql", url)


def offline_sql(current: str | None) -> str:
    start = current if current else "base"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", f"{start}:head", "--sql"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise SystemExit(f"Could not generate the migration SQL offline:\n{result.stderr[-1500:]}")
    return "\n".join(
        line for line in result.stdout.splitlines()
        if line.strip() not in TRANSACTION_MARKERS and not re.match(r"^(INFO|WARNING|DEBUG|ERROR)\s+\[|^\[[A-Z_]+\]", line)
    )


async def rehearse(url: str, head: str) -> tuple[bool, str | None]:
    """Return (passed, current_revision)."""
    connection = await asyncpg.connect(url, statement_cache_size=0, timeout=60)
    try:
        has_table = await connection.fetchval("select to_regclass('alembic_version') is not null")
        current = await connection.fetchval("select version_num from alembic_version") if has_table else None
        print(f"database revision: {current} | head: {head}")
        if current == head:
            print("already at head: nothing to apply.")
            return True, current
        sql = offline_sql(current)
        print(f"generated {len(sql.splitlines())} lines of SQL for {current} -> {head} (offline, nothing executed yet)")
        transaction = connection.transaction()
        await transaction.start()
        try:
            await connection.execute(sql)
            print("all pending migrations ran inside the rehearsal transaction")
        except Exception as error:  # noqa: BLE001 - any error means the rehearsal failed
            print(f"REHEARSAL FAILED: {type(error).__name__}: {str(error)[:400]}")
            return False, current
        finally:
            await transaction.rollback()
        after = await connection.fetchval("select version_num from alembic_version") if has_table else None
        print(f"rolled back: revision is still {after}")
        if after != current:
            print("REHEARSAL FAILED: the rollback did not restore the revision")
            return False, current
        print("REHEARSAL PASSED")
        return True, current
    finally:
        await connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="after a passed rehearsal, run `alembic upgrade head` for real")
    args = parser.parse_args(argv)
    passed, current = asyncio.run(rehearse(database_url(), head_revision()))
    if not passed:
        return 1
    if not args.apply:
        print("Rehearsal only. Re-run with --apply to commit the migrations.")
        return 0
    if current == head_revision():
        return 0
    print("Applying for real: alembic upgrade head")
    return subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
