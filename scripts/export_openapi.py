"""Regenerate docs/api/openapi.json from the live FastAPI app.

`tests/docs/test_api_reference.py` fails when the committed export's set of paths
differs from `api.main.app.openapi()`; run this after any router change:

    python scripts/export_openapi.py            # rewrite docs/api/openapi.json
    python scripts/export_openapi.py --check    # exit 1 if it is stale, write nothing

Output format matches the committed file (2-space indent, CRLF line endings).
Importing `api.main` loads the whole application, so expect a few hundred MB of RAM.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "api" / "openapi.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only report whether the committed export is stale")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from api.main import app  # noqa: E402

    live = app.openapi()
    committed = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {"paths": {}}
    added = sorted(set(live["paths"]) - set(committed["paths"]))
    removed = sorted(set(committed["paths"]) - set(live["paths"]))
    print(f"live paths: {len(live['paths'])}, committed paths: {len(committed['paths'])}, added: {len(added)}, removed: {len(removed)}")
    for path in added:
        print("  + ", path)
    for path in removed:
        print("  - ", path)

    if args.check:
        return 1 if (added or removed) else 0
    with open(TARGET, "w", encoding="utf-8", newline="\r\n") as handle:
        json.dump(live, handle, indent=2)
        handle.write("\n")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
