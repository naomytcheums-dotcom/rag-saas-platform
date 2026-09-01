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

import html
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


def send_account_restore_email(to_email: str, restore_link: str) -> None:
    """Called by api/services/account_restore.py with a link containing
    the raw (not hashed) restore token -- lets a user undo
    DELETE /account/me before api/tasks/account_purge.py permanently
    erases their data at the end of the grace period."""
    _send(
        to_email,
        subject="Restore your account",
        html=(
            f"<p>We received a request to restore your deactivated "
            f"account. Click the link below to reactivate it. It expires "
            f"in {settings.ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES // 60} hours.</p>"
            f'<p><a href="{restore_link}">{restore_link}</a></p>'
            f"<p>If you didn't request this, you can safely ignore this "
            f"email -- your account will remain deactivated and will be "
            f"permanently deleted as originally scheduled.</p>"
        ),
    )


def send_two_factor_lockout_recovery_requested_email(to_email: str, confirm_link: str, delay_hours: int) -> None:
    """
    Called by api/services/two_factor_lockout_recovery.py right after
    POST /auth/2fa/lockout-recovery/request accepts a correct email +
    password for an account that still has 2FA enabled. This is a
    high-stakes email on purpose -- it's sent even to legitimate users,
    since the whole point of the mandatory delay is giving the real
    owner a chance to notice and cancel it (by logging in normally) if
    they didn't request it themselves.
    """
    _send(
        to_email,
        subject="Two-factor authentication removal requested",
        html=(
            f"<p>Someone just requested to remove two-factor authentication "
            f"from your account, using the correct account password.</p>"
            f"<p>This will NOT take effect immediately. The link below only "
            f"becomes active in {delay_hours} hours, and expires a few days "
            f"after that.</p>"
            f'<p><a href="{confirm_link}">{confirm_link}</a></p>'
            f"<p><strong>If this was you</strong> -- for example because you "
            f"lost your authenticator device and your recovery codes -- no "
            f"further action is needed until the link becomes active.</p>"
            f"<p><strong>If this wasn't you</strong>, log in normally right "
            f"now with your authenticator app or a recovery code: doing so "
            f"cancels this request immediately. Since whoever made this "
            f"request knows your password, you should also change it.</p>"
        ),
    )


def send_two_factor_lockout_recovery_completed_email(to_email: str) -> None:
    """Called once POST /auth/2fa/lockout-recovery/confirm actually
    disables 2FA -- the account is now back to password-only login, so
    this is worth flagging clearly even though the requesting email
    already warned this was coming."""
    _send(
        to_email,
        subject="Two-factor authentication has been disabled on your account",
        html=(
            "<p>Two-factor authentication has just been disabled on your "
            "account through the lockout recovery process, and every "
            "device has been logged out.</p>"
            "<p>If you meant to do this, you can log in with just your "
            "password now, and set up 2FA again from your account "
            "settings whenever you're ready.</p>"
            "<p>If you did NOT mean for this to happen, someone else knows "
            "your password -- log in immediately, change your password, "
            "and set up two-factor authentication again.</p>"
        ),
    )


def send_new_login_notification_email(to_email: str, device_info: str | None, ip_address: str | None, when: str) -> None:
    """
    Called by api/security/sessions.py's issue_session() the first time a
    session is created from a device (User-Agent) this account hasn't
    used before -- login, refresh from an unrecognized device, OAuth, or
    post-2FA verification, but deliberately not registration (a brand
    new account has no "usual" device to compare against, so every
    login would otherwise look "new").

    device_info comes straight from the caller-supplied User-Agent
    header -- untrusted input -- so it's HTML-escaped before going into
    the email body, same reasoning as escaping any other
    attacker-controllable string dropped into HTML.
    """
    safe_device = html.escape(device_info) if device_info else "an unknown device"
    safe_ip = html.escape(ip_address) if ip_address else "an unknown location"
    _send(
        to_email,
        subject="New sign-in to your account",
        html=(
            f"<p>Your account was just signed into from a new device.</p>"
            f"<p><strong>When:</strong> {html.escape(when)}<br>"
            f"<strong>Device:</strong> {safe_device}<br>"
            f"<strong>IP address:</strong> {safe_ip}</p>"
            f"<p>If this was you, no action is needed. If it wasn't, reset your "
            f"password immediately and review your active sessions.</p>"
        ),
    )


def send_recovery_code_used_email(to_email: str) -> None:
    """
    Called by api/routers/two_factor.py's verify_two_factor_recovery_code()
    every time a recovery code successfully completes a login. Worth
    flagging on its own, separate from issue_session()'s new-device
    check: using a recovery code means the authenticator app itself was
    NOT used to log in, which is unusual even from an already-recognized
    device/browser.
    """
    _send(
        to_email,
        subject="A 2FA recovery code was used on your account",
        html=(
            "<p>Someone just signed in to your account using a two-factor "
            "recovery code instead of your authenticator app.</p>"
            "<p>If this was you -- for example because you lost access to "
            "your authenticator device -- consider generating a fresh set "
            "of recovery codes once you're set up again, since each code "
            "only works once.</p>"
            "<p>If this wasn't you, someone may have obtained your "
            "recovery codes. Reset your password immediately and "
            "regenerate your 2FA secret and recovery codes.</p>"
        ),
    )


def send_consent_withdrawn_email(to_email: str) -> None:
    """
    Called by api/routers/account.py's withdraw_consent() -- an RGPD/GDPR
    data-subject-rights acknowledgment confirming the request was
    received and acted on. Deliberately distinguishes this from a full
    deletion: withdrawing consent deactivates the account but does not
    erase any data, and a user who only meant to object to processing
    (not lose their data) shouldn't be left thinking otherwise.
    """
    _send(
        to_email,
        subject="Your consent withdrawal has been processed",
        html=(
            "<p>We've received your request to withdraw consent to data "
            "processing and deactivated your account immediately.</p>"
            "<p>Your account data has not been deleted -- deactivating is "
            "not the same as erasing your data. If you'd also like your "
            "data permanently deleted, please contact support.</p>"
            "<p>If you did not request this, please contact support "
            "immediately -- your account is currently deactivated and "
            "inaccessible.</p>"
        ),
    )


def send_consent_reactivation_email(to_email: str, reactivation_link: str) -> None:
    """Called by api/services/consent_reactivation.py with a link
    containing the raw (not hashed) token -- lets a user who withdrew
    consent (POST /account/consent/withdraw) come back, without that
    being a silent one-way door."""
    _send(
        to_email,
        subject="Reactivate your account",
        html=(
            f"<p>We received a request to reactivate your account, which "
            f"was deactivated after you withdrew consent to data processing.</p>"
            f"<p>Click the link below to accept the current terms of "
            f"service again and reactivate your account.</p>"
            f'<p><a href="{reactivation_link}">{reactivation_link}</a></p>'
            f"<p>If you didn't request this, you can safely ignore this "
            f"email -- your account will remain deactivated.</p>"
        ),
    )


def send_password_set_email(to_email: str) -> None:
    """
    Called by api/routers/account.py's set_password() -- adding a
    password to what was previously an OAuth-only account is a real
    change to the account's attack surface (a whole new login method
    now exists), so it's worth a confirmation email the same way a
    password reset or 2FA change gets one, even though the account owner
    is the one who just did this from an authenticated session.
    """
    _send(
        to_email,
        subject="A password was added to your account",
        html=(
            "<p>A password was just added to your account. You can now "
            "log in with your email and this password, in addition to "
            "however you signed in before (Google/GitHub).</p>"
            "<p>If you didn't do this, someone with access to your "
            "account just gave themselves a second way back in -- "
            "review your account's active sessions immediately and "
            "revoke anything you don't recognize.</p>"
        ),
    )


def send_rate_limit_alert_email(to_email: str, context: str) -> None:
    """
    Called when the *email-scoped* login rate limit trips (see
    api/routers/auth.py's login()) -- an IP-scoped trip isn't notified
    the same way, since it says nothing specific about this particular
    account being targeted. `context` is a short, fixed, non-user-supplied
    string describing what was being attempted (e.g. "sign-in") -- never
    interpolate request-controlled data here without escaping it first.
    """
    _send(
        to_email,
        subject="Repeated failed attempts on your account",
        html=(
            f"<p>We've blocked several failed {context} attempts on your account "
            f"in the last few minutes.</p>"
            f"<p>If this wasn't you, no action is needed right now -- the attempts "
            f"were blocked and your account was not accessed. If you're concerned, "
            f"consider changing your password.</p>"
        ),
    )
