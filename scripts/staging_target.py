"""Validate the explicitly allowlisted staging target without loading api settings."""

from __future__ import annotations

import os
from base64 import urlsafe_b64encode
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

ROOT = Path(__file__).resolve().parent.parent
STAGING_HOST = "db.<STAGING_PROJECT_REF>.supabase.co"
STAGING_POOLER_HOST = "<STAGING_POOLER_HOST>"
STAGING_POOLER_USER = "<STAGING_DB_USER>"
STAGING_ENV = ROOT / ".env.staging"


class StagingTargetError(ValueError):
    pass


def validate_staging_url(value: str) -> URL:
    try:
        url = make_url(value)
    except (ArgumentError, ValueError):
        raise StagingTargetError("Invalid staging URL; input is not logged.") from None
    if (
        url.drivername not in {"postgresql", "postgresql+asyncpg"}
        or (url.host, url.username) not in {
            (STAGING_HOST, "postgres"),
            (STAGING_POOLER_HOST, STAGING_POOLER_USER),
        }
        or url.port != 5432
        or url.database != "postgres"
        or (url.query and dict(url.query) != {"ssl": "require"})
    ):
        raise StagingTargetError("Target refused: only the exact staging direct or session-pooler target is allowed.")
    if not url.password or "[" in url.password or url.password == "YOUR-STAGING-PASSWORD":
        raise StagingTargetError("Staging credential is not provisioned locally; no connection attempted.")
    return url.set(drivername="postgresql+asyncpg", query={"ssl": "require"})


def staging_url() -> URL:
    if not STAGING_ENV.is_file():
        raise StagingTargetError(".env.staging is missing; no fallback to .env is allowed.")
    values = dotenv_values(STAGING_ENV)
    if values.get("ENVIRONMENT") != "staging":
        raise StagingTargetError(".env.staging must declare ENVIRONMENT=staging.")
    value = os.environ.get("STAGING_DATABASE_URL") or values.get("DATABASE_URL")
    if not value:
        raise StagingTargetError("Staging DATABASE_URL is missing.")
    return validate_staging_url(value)


def isolated_environment(url: URL) -> dict[str, str]:
    """Use only staging dotenv values and fresh, process-local test keys."""
    import secrets

    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE",
                   "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "COMSPEC", "PATHEXT"}
    }
    env.update({
        "RAG_ENV_FILE": str(STAGING_ENV),
        "PYTHON_DOTENV_DISABLED": "1",
        "DATABASE_URL": url.render_as_string(hide_password=False),
        "STAGING_DATABASE_URL": url.render_as_string(hide_password=False),
        "DATABASE_URL_TRANSACTION": "",
        "ENVIRONMENT": "staging",
        "JWT_SECRET_KEY": secrets.token_hex(32),
        "SESSION_MIDDLEWARE_SECRET": secrets.token_hex(32),
        "AUDIT_LOG_HMAC_SECRET_KEY": secrets.token_hex(32),
        "SECRET_ENCRYPTION_KEY": urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"),
        "ENCRYPTION_MASTER_KEY": urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"),
        "SUPPORT_EMAIL": "staging-test@example.invalid",
        "SENTRY_ENVIRONMENT": "staging",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
        "AWS_EC2_METADATA_DISABLED": "true",
        "AWS_SHARED_CREDENTIALS_FILE": str(ROOT / "staging-artifacts" / "no-aws-credentials"),
        "AWS_CONFIG_FILE": str(ROOT / "staging-artifacts" / "no-aws-config"),
        "PYTHONIOENCODING": "utf-8",
    })
    return env
