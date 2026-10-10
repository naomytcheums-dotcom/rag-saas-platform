"""Bundle the translations into the frontend: locales/<lang>/*.json (the source the API serves) -> frontend/lib/locales/<lang>.json.

The frontend used to show raw keys ("landing.hero.title_line1") until GET /i18n/translations/<lang> answered. The bundled copy is the instant
first value of the translation context, so no page ever renders a key, even when the API is slow or down. The API response still overrides it.

    python scripts/sync_frontend_locales.py          # rewrite the bundled files
    python scripts/sync_frontend_locales.py --check  # exit 1 when they are out of date (used by the frontend test)
"""
import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ("en", "fr")


def merged(language: str) -> dict:
    result: dict = {}
    for path in sorted(glob.glob(str(ROOT / "locales" / language / "*.json"))):
        result.update(json.loads(Path(path).read_text(encoding="utf-8")))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target_dir = ROOT / "frontend" / "lib" / "locales"
    target_dir.mkdir(parents=True, exist_ok=True)
    stale = []
    for language in LANGUAGES:
        text = json.dumps(merged(language), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
        target = target_dir / f"{language}.json"
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                stale.append(language)
        else:
            target.write_text(text, encoding="utf-8", newline="\n")
    if args.check and stale:
        print(f"Bundled translations out of date for: {', '.join(stale)}. Run: python scripts/sync_frontend_locales.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
