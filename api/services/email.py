"""
Transactional email via Resend's plain REST API (no SDK dependency --
project already leans on httpx directly elsewhere, e.g. src/agent.py's
GitHub calls).

Callers (the auth routers) treat a failed send as non-fatal: an account
should still get created / a reset should still be usable via the token
even if the email bounces or Resend is unreachable, so every function here
raises on failure rather than swallowing it, and it's the router's job to
catch, log, and continue -- never let email delivery be a single point of
failure for account creation.
"""

import logging

import httpx

from api.config import settings

RESEND_API_URL = "https://api.resend.com/emails"
EMAIL_TIMEOUT_SECONDS = 10.0

logger = logging.getLogger(__name__)


def _send(to_email: str, subject: str, html: str) -> None:
    """Low-level Resend API call shared by send_password_reset_email and
    send_verification_code_email below -- both just build the HTML body
    and delegate here. Raises on any failure (missing key, timeout, bad
    response, unreachable) rather than swallowing it -- see this
    module's top docstring for why the *callers* are the ones who decide
    to catch and log instead of propagating further."""
    if not settings.RESEND_API_KEY:
        raise EnvironmentError(
            "RESEND_API_KEY is not set -- get one from https://resend.com/api-keys "
            "and set it in .env as RESEND_API_KEY=re_..."
        )
    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={"from": settings.EMAIL_FROM_ADDRESS, "to": [to_email], "subject": subject, "html": html},
            timeout=EMAIL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Resend request timed out after {EMAIL_TIMEOUT_SECONDS}s") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Resend returned an error (status {exc.response.status_code}): {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("Could not reach Resend -- check network connectivity") from exc


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """Called by api/services/password_reset.py with a link containing
    the raw (not hashed) reset token."""
    _send(
        to_email,
        subject="Reset your password",
        html=(
            f"<p>Click the link below to reset your password. It expires in "
            f"{settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.</p>"
            f'<p><a href="{reset_link}">{reset_link}</a></p>'
            f"<p>If you didn't request this, you can safely ignore this email.</p>"
        ),
    )


def send_verification_code_email(to_email: str, code: str) -> None:
    """Called by api/services/verification.py with the raw (not hashed)
    6-digit code."""
    _send(
        to_email,
        subject="Your verification code",
        html=(
            f"<p>Your verification code is:</p>"
            f"<p style='font-size:24px;font-weight:bold;letter-spacing:4px'>{code}</p>"
            f"<p>It expires in {settings.EMAIL_OTP_EXPIRE_MINUTES} minutes.</p>"
        ),
    )
