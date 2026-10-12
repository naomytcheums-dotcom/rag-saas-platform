"""Mask the secrets already stored in `system_logs` (SEC-009, phase 5 of the 2026-10-12 security audit).

The masking of log lines was incomplete before 2026-10-12 (only the quoted form, only in two places), so rows written until then can still hold a
`Bearer` header, a `password=...` pair, a credential inside a URL, a provider key or one of this deployment's own configured secrets.

    python scripts/scrub_system_logs.py                          # DRY RUN (default): counts only, writes nothing, prints no log content
    python scripts/scrub_system_logs.py --apply --confirm-database <database name>

Run it yourself, with the DATABASE_URL (and the usual secrets, so that THIS deployment's own secrets are recognised by value) of the database to clean.
`--apply` requires the exact name of the database as a second, deliberate confirmation. Only the `message` column of rows that actually change is
updated; rows are processed in batches of one transaction each, and a second pass must find nothing left. Hosted Loki / Grafana Cloud copies cannot be
edited from here: shorten their retention or delete the streams in Grafana Cloud.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def scrub(engine, apply: bool = False, batch_size: int = 500, mask=None) -> dict:
    """Scan `system_logs` by primary key and return {"scanned", "affected", "updated", "by_level"}. Never returns or prints a message."""
    from sqlalchemy import text

    if mask is None:
        from api.security.logging_correlation import mask_sensitive as mask

    scanned = affected = updated = 0
    by_level: dict[str, int] = {}
    last_id = None
    while True:
        with engine.begin() as conn:
            query = "SELECT id, level, message FROM system_logs" + (" WHERE id > :last" if last_id is not None else "") + " ORDER BY id LIMIT :n"
            rows = conn.execute(text(query), {"last": last_id, "n": batch_size} if last_id is not None else {"n": batch_size}).fetchall()
            if not rows:
                break
            for row_id, level, message in rows:
                scanned += 1
                masked = mask(message or "")
                if masked != (message or ""):
                    affected += 1
                    by_level[level] = by_level.get(level, 0) + 1
                    if apply:
                        conn.execute(text("UPDATE system_logs SET message = :m WHERE id = :i"), {"m": masked, "i": row_id})
                        updated += 1
            last_id = rows[-1][0]
    return {"scanned": scanned, "affected": affected, "updated": updated, "by_level": by_level}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="really update the rows (default: dry run)")
    parser.add_argument("--confirm-database", help="exact name of the database, required with --apply")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(ROOT))
    from sqlalchemy import create_engine

    from api.config import settings
    from api.database_url import synchronous_database_url

    url = synchronous_database_url(settings.DATABASE_URL) if settings.DATABASE_URL.startswith("postgresql") else settings.DATABASE_URL
    engine = create_engine(url)
    database = engine.url.database
    if args.apply and args.confirm_database != database:
        print(f"Refusing: --apply needs --confirm-database {database!r} (the exact name of the database this DATABASE_URL points to).", file=sys.stderr)
        return 2
    print(f"database: {database} ({'APPLY' if args.apply else 'dry run, nothing is written'})")
    first = scrub(engine, apply=args.apply, batch_size=args.batch_size)
    print(f"scanned {first['scanned']} rows; rows holding a secret: {first['affected']}; by level: {first['by_level']}; updated: {first['updated']}")
    if args.apply:
        second = scrub(engine, apply=False, batch_size=args.batch_size)
        print(f"second pass: rows still holding a secret: {second['affected']}")
        return 0 if second["affected"] == 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
