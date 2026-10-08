"""Report configuration presence only; never import API settings or connect."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
VARIABLES = (
    "S3_ENDPOINT_URL", "S3_REGION", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY",
    "S3_BUCKET_NAME", "S3_DOCUMENTS_BUCKET_NAME", "S3_VOICE_BUCKET_NAME",
    "STAGING_ALLOWED_DIRECT_HOST", "STAGING_ALLOWED_POOLER_HOST",
    "STAGING_ALLOWED_POOLER_USER", "STAGING_DATABASE_URL",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MISTRAL_API_KEY", "GEMINI_API_KEY",
    "WATSONX_API_KEY", "OPENAI_COMPATIBLE_API_KEY", "OPENAI_EMBEDDING_API_KEY",
    "VOYAGE_API_KEY", "COHERE_API_KEY", "RESEND_API_KEY",
    "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET",
    "STRIPE_API_VERSION", "STRIPE_SUCCESS_URL", "STRIPE_CANCEL_URL",
    "STRIPE_PORTAL_RETURN_URL", "PAYSTACK_SECRET_KEY", "PAYSTACK_PUBLIC_KEY",
    "PAYSTACK_CALLBACK_URL", "PAYSTACK_COUNTRIES", "METRICS_AUTH_TOKEN",
    "DISCORD_GATEWAY_SHARED_SECRET", "TEAMS_BOT_ID",
)


def load_values() -> dict[str, str | None]:
    """Use only the ignored staging dotenv, with process overrides."""
    values = dict(dotenv_values(ROOT / ".env.staging"))
    values.update(os.environ)
    return values


def bracketed_password(values: dict[str, str | None]) -> bool:
    for name in ("STAGING_DATABASE_URL", "DATABASE_URL", "DATABASE_URL_TRANSACTION"):
        value = values.get(name)
        if not value:
            continue
        try:
            password = unquote(urlsplit(value).password or "")
        except ValueError:
            # Invalid URLs are not echoed; readiness must still be refused.
            return True
        if "[" in password or "]" in password:
            return True
    return False


def report(values: dict[str, str | None]) -> bool:
    names = sorted(set(VARIABLES) | {
        name for name in values
        if name.startswith(("S3_", "STAGING_ALLOWED_", "STRIPE_", "PAYSTACK_"))
        and name.isidentifier()
    })
    missing = []
    for name in names:
        present = bool((values.get(name) or "").strip())
        print(f"{name}={'PRESENT' if present else 'MISSING'}")
        if not present:
            missing.append(name)
    placeholder = bracketed_password(values)
    print(f"DATABASE_PASSWORD_PLACEHOLDER={placeholder}")
    if missing or placeholder:
        print("NEXT_ACTION=Provision missing settings in the process or ignored .env.staging; "
              "replace placeholder database passwords locally. No connection attempted.")
    else:
        print("NEXT_ACTION=Run the guarded staging runner preflight; presence does not validate "
              "credentials, allowlist, provider choice or permissions. No connection attempted.")
    return not missing and not placeholder


def main() -> int:
    return 0 if report(load_values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
