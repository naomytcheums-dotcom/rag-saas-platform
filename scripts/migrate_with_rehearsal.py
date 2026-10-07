"""Apply the pending Alembic migrations to the database named in `.env`, after proving them on that very database.

    python scripts/migrate_with_rehearsal.py            # rehearsal only: everything runs inside ONE transaction that is ALWAYS rolled back
    python scripts/migrate_with_rehearsal.py --apply    # the rehearsal, then (only if every check passed) `alembic upgrade head` for real

The rehearsal generates the SQL of every pending migration offline (`alembic upgrade <current>:head --sql`), runs it against the real
PostgreSQL server (transactional DDL), then exercises the 0133 triggers with real writes on a copy of an existing chunk (UPDATE, INSERT,
DELETE: each must bump the organization's `bm25_corpus_revision` by exactly one), and rolls everything back. Nothing is committed unless
`--apply` is given AND the rehearsal passed. No credential is ever printed.
"""

import argparse
import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

import asyncpg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
TRANSACTION_MARKERS = {"BEGIN;", "COMMIT;"}


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env").get("DATABASE_URL")
    if not url:
        raise SystemExit("No DATABASE_URL in the environment or in .env")
    return re.sub(r"^postgresql\+asyncpg", "postgresql", url)


def _offline_sql(current: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", f"{current}:head", "--sql"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise SystemExit(f"Could not generate the migration SQL offline:\n{result.stderr[-1500:]}")
    return "\n".join(line for line in result.stdout.splitlines() if line.strip() not in TRANSACTION_MARKERS)


async def _revision_of(conn, organization_id) -> int:
    return await conn.fetchval("select bm25_corpus_revision from organizations where id = $1", organization_id)


async def _rehearse(url: str) -> tuple[bool, str]:
    conn = await asyncpg.connect(url, statement_cache_size=0, timeout=60)
    try:
        current = await conn.fetchval("select version_num from alembic_version")
        print(f"[1/5] database revision: {current} | role: {await conn.fetchval('select current_user')} "
              f"| size: {await conn.fetchval('select pg_database_size(current_database())/1024/1024')} MB")
        if current == "0133":
            print("      already at 0133 or later: nothing to apply.")
            return True, current
        sql = _offline_sql(current)
        print(f"[2/5] generated {len(sql.splitlines())} lines of SQL for {current} -> head (offline, nothing executed yet)")
        failures = []
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute(sql)
            print("[3/5] all pending migrations ran inside the rehearsal transaction")
            triggers = await conn.fetchval("select count(*) from pg_trigger where tgname like 'bm25_revision_%'")
            if triggers != 9:
                failures.append(f"expected 9 bm25_revision triggers, found {triggers}")
            row = await conn.fetchrow("select id, organization_id from document_chunks order by created_at desc nulls last limit 1") \
                if await conn.fetchval("select count(*) from information_schema.columns where table_name='document_chunks' and column_name='created_at'") \
                else await conn.fetchrow("select id, organization_id from document_chunks limit 1")
            if row is None:
                print("[4/5] no chunk exists to copy: trigger behaviour NOT exercised (syntax only)")
            else:
                chunk_id, org = row["id"], row["organization_id"]
                base = await _revision_of(conn, org)
                await conn.execute("update document_chunks set chunk_index = chunk_index where id = $1", chunk_id)
                after_update = await _revision_of(conn, org)
                await conn.execute("create temp table _rehearsal_copy on commit drop as select * from document_chunks where id = $1", chunk_id)
                await conn.execute("update _rehearsal_copy set id = gen_random_uuid()")
                await conn.execute("insert into document_chunks select * from _rehearsal_copy")
                after_insert = await _revision_of(conn, org)
                await conn.execute("delete from document_chunks where id = (select id from _rehearsal_copy)")
                after_delete = await _revision_of(conn, org)
                steps = [base, after_update, after_insert, after_delete]
                print(f"[4/5] revision after update/insert/delete: {steps}")
                if steps != [base, base + 1, base + 2, base + 3]:
                    failures.append(f"each write must bump the revision by exactly 1, got {steps}")
        except Exception as exc:  # noqa: BLE001 -- any error means the rehearsal failed
            failures.append(f"{type(exc).__name__}: {str(exc)[:300]}")
        finally:
            await tr.rollback()
        still = await conn.fetchval("select count(*) from information_schema.columns where table_name='organizations' and column_name='bm25_corpus_revision'")
        print(f"[5/5] rolled back: bm25_corpus_revision column present afterwards = {bool(still)} (must be False if 0133 was pending)")
        if failures:
            print("REHEARSAL FAILED:\n  - " + "\n  - ".join(failures))
            return False, current
        print("REHEARSAL PASSED")
        return True, current
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="after a passed rehearsal, run `alembic upgrade head` for real")
    args = parser.parse_args()
    ok, current = asyncio.run(_rehearse(_database_url()))
    if not ok:
        return 1
    if not args.apply or current == "0133":
        if not args.apply:
            print("Rehearsal only. Re-run with --apply to commit the migrations.")
        return 0
    print("Applying for real: alembic upgrade head")
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
