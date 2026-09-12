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
from api.models.custom_domain import CustomDomain

RESEND_API_URL = "https://api.resend.com/emails"
EMAIL_TIMEOUT_SECONDS = 10.0

logger = logging.getLogger(__name__)


def _send(to_email: str, subject: str, html: str, from_address: str | None = None) -> None:
    """Low-level Resend API call shared by every send_*_email function in
    this module -- each just builds the HTML body and delegates here.
    Raises on any failure (missing key, timeout, bad response,
    unreachable) rather than swallowing it -- see this module's top
    docstring for why the *callers* are the ones who decide to catch and
    log instead of propagating further.

    `from_address` defaults to settings.EMAIL_FROM_ADDRESS (every
    existing call site in this module) -- Partie 1.4.5's
    send_via_custom_email_domain below is the one exception, passing an
    organization's own verified custom domain instead.

    Appends a support-contact footer to every single email this app
    sends, unconditionally -- RGPD Art. 12 requires that a data subject
    can easily reach the controller to exercise their rights or ask
    questions, and that requirement doesn't stop at the handful of
    emails someone remembered to add a contact line to by hand. One
    change here covers every email this module has ever sent AND every
    one a future call site adds, rather than relying on each new
    send_*_email function to remember it individually.
    """
    if not settings.RESEND_API_KEY:
        raise EnvironmentError(
            "RESEND_API_KEY is not set -- get one from https://resend.com/api-keys "
            "and set it in .env as RESEND_API_KEY=re_..."
        )
    body_with_footer = (
        f"{html}"
        f"<p style='color:#666;font-size:12px;margin-top:24px;border-top:1px solid #eee;padding-top:12px'>"
        f"Questions about this email or your account? Contact us at "
        f"<a href='mailto:{settings.SUPPORT_EMAIL}'>{settings.SUPPORT_EMAIL}</a>.</p>"
    )
    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={"from": from_address or settings.EMAIL_FROM_ADDRESS, "to": [to_email], "subject": subject, "html": body_with_footer},
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


def send_idle_session_revoked_email(to_email: str) -> None:
    """
    Audit finding 13 -- called by api/dependencies.py when a request
    arrives on a session that's been idle longer than
    SESSION_IDLE_TIMEOUT_MINUTES, right before that session is revoked.
    A courtesy notice, not a security alert on its own (unlike a new-
    device sign-in, an idle timeout is the EXPECTED outcome of walking
    away from a device) -- but still worth surfacing so "why was I
    logged out" has an answer instead of looking like a bug.
    """
    _send(
        to_email,
        subject="You were signed out due to inactivity",
        html=(
            "<p>One of your sessions was automatically signed out after "
            "a period of inactivity, as a security precaution.</p>"
            "<p>If you're still using that device, just log in again to "
            "continue. If you don't recognize this activity at all, "
            "review your active sessions and change your password.</p>"
        ),
    )


def send_concurrent_session_limit_reached_email(to_email: str, revoked_device_info: str | None) -> None:
    """
    Audit finding 14 -- called by api/security/sessions.py's
    enforce_concurrent_session_limit() every time a new sign-in pushes
    the account over MAX_CONCURRENT_SESSIONS and an older session gets
    revoked to make room. revoked_device_info is the same untrusted
    User-Agent string as send_new_login_notification_email's
    device_info -- HTML-escaped for the same reason.
    """
    safe_device = html.escape(revoked_device_info) if revoked_device_info else "an unknown device"
    _send(
        to_email,
        subject="One of your sessions was signed out (device limit reached)",
        html=(
            f"<p>You just signed in on a new device, and your account "
            f"reached its limit of simultaneous sessions. Your oldest "
            f"session was signed out to make room:</p>"
            f"<p><strong>Device signed out:</strong> {safe_device}</p>"
            f"<p>If that wasn't expected, review your active sessions "
            f"and change your password.</p>"
        ),
    )


def send_two_factor_enabled_email(to_email: str) -> None:
    """
    Called by api/routers/two_factor.py's enable_two_factor() every time
    2FA is turned on. Not just a courtesy notification: /setup returns
    the TOTP secret in plaintext to anyone holding a valid access token,
    and /enable only needs a code derived from it -- an attacker with a
    stolen token could scan that QR code into their own authenticator
    and enable 2FA under a secret only they control, locking the real
    owner out before anything else looks wrong. This email is what lets
    the real owner notice and react in time.
    """
    _send(
        to_email,
        subject="Two-factor authentication was just enabled on your account",
        html=(
            "<p>Two-factor authentication was just turned on for your "
            "account. From now on, logging in requires a code from your "
            "authenticator app (or one of your recovery codes), in "
            "addition to your password.</p>"
            "<p>If you just set this up yourself, no action is needed.</p>"
            "<p>If you did NOT do this, someone else may have access to "
            "your account and could be locking you out of it right now. "
            "Act immediately: use the recovery link to remove 2FA with "
            "your password (POST /auth/2fa/lockout-recovery/request), "
            "then change your password as soon as you're back in.</p>"
        ),
    )


def send_two_factor_disabled_email(to_email: str) -> None:
    """
    Called by api/routers/two_factor.py's disable_two_factor() every
    time 2FA is turned off. Turning off 2FA already requires a valid
    current TOTP code (not just an access token), so whoever did this
    already had strong proof of controlling the account -- but that's
    exactly the scenario worth flagging anyway: a stolen unlocked device
    with the authenticator app already open, or a compromised session
    right after 2FA was set up, could do this before the real owner
    notices anything else is wrong.
    """
    _send(
        to_email,
        subject="Two-factor authentication was just disabled on your account",
        html=(
            "<p>Two-factor authentication was just turned off for your "
            "account. From now on, your password alone is enough to log "
            "in.</p>"
            "<p>If you just did this yourself, no action is needed.</p>"
            "<p>If you did NOT do this, someone with access to your "
            "authenticator app or a valid code just removed your "
            "account's second layer of protection. Change your password "
            "immediately and set up two-factor authentication again.</p>"
        ),
    )


def send_recovery_codes_regenerated_email(to_email: str) -> None:
    """
    Called by api/routers/two_factor.py's regenerate_recovery_codes()
    every time a fresh batch of recovery codes is issued. Same
    reasoning as send_two_factor_disabled_email above: this requires a
    valid current TOTP code, so it's already a stronger action than a
    stolen access token alone could take -- but it's also exactly what
    someone who DOES control the TOTP could use to quietly invalidate
    every recovery code the real owner saved, cutting off their fallback
    without touching TOTP itself.
    """
    _send(
        to_email,
        subject="Your two-factor recovery codes were regenerated",
        html=(
            "<p>A new set of two-factor recovery codes was just "
            "generated for your account. Your previous codes no longer "
            "work.</p>"
            "<p>If you just did this yourself, no action is needed -- "
            "just make sure you saved the new codes somewhere safe.</p>"
            "<p>If you did NOT do this, someone with access to your "
            "authenticator app just replaced your recovery codes. "
            "Change your password immediately.</p>"
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


def send_account_deletion_scheduled_email(to_email: str, deletion_scheduled_at_iso: str) -> None:
    """
    Called by api/routers/account.py's delete_account() immediately when
    a user requests deletion (4.6) -- the FIRST of two distinct warnings
    before permanent deletion, confirming the request landed and giving
    the exact date restoring is still possible until. The second is
    send_account_deletion_reminder_email below, sent by a scheduled task
    closer to the actual purge -- a single email 30 days out is easy to
    forget by the time it matters.
    """
    _send(
        to_email,
        subject="Your account is scheduled for deletion",
        html=(
            f"<p>We've received your request to delete your account. It "
            f"has been deactivated immediately, and is scheduled for "
            f"permanent deletion on <strong>{html.escape(deletion_scheduled_at_iso)}</strong>.</p>"
            f"<p>Changed your mind? You can restore your account any time "
            f"before that date -- use the account restore option (POST "
            f"/account/restore/request with your email) to get a link.</p>"
            f"<p>If you didn't request this, restore your account "
            f"immediately using the same option and change your password "
            f"once you're back in.</p>"
        ),
    )


def send_account_deletion_reminder_email(to_email: str, days_remaining: int) -> None:
    """
    Called by api/tasks/account_deletion_reminder.py's daily sweep (4.6)
    -- the second, closer-to-the-deadline warning before permanent
    deletion, for a user who requested deletion and hasn't restored
    their account since. Sent once per deletion cycle (see
    User.deletion_reminder_sent_at), not once a day for the whole
    remaining window.
    """
    _send(
        to_email,
        subject="Your account will be permanently deleted soon",
        html=(
            f"<p>This is a reminder: your account is scheduled for "
            f"permanent deletion in approximately {days_remaining} day"
            f"{'s' if days_remaining != 1 else ''}. Once that happens, "
            f"your data cannot be recovered.</p>"
            f"<p>If you'd like to keep your account, restore it now -- "
            f"use the account restore option (POST /account/restore/request "
            f"with your email) to get a link.</p>"
            f"<p>If you do want your account deleted, no action is "
            f"needed -- it will be removed automatically as scheduled.</p>"
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


def send_password_changed_email(to_email: str) -> None:
    """
    Called by api/routers/account.py's change_password() every time an
    already-logged-in user rotates their password via their current one
    (not the forgot/reset email flow, which has its own implicit
    notification -- the reset link itself only reaches the real
    mailbox). change_password() already revokes every session as part of
    the same call, so this is a courtesy confirmation, not the primary
    signal something is wrong -- but if the current password was itself
    obtained illegitimately (e.g. shoulder-surfed), this is still worth
    flagging to the real owner.
    """
    _send(
        to_email,
        subject="Your password was changed",
        html=(
            "<p>Your account password was just changed. Every device has "
            "been logged out, including this one -- log in again with "
            "your new password.</p>"
            "<p>If you didn't do this, someone else knows your password. "
            "Reset it immediately using the \"forgot password\" option, "
            "which will log out whoever made this change too.</p>"
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


def send_security_alert_email(to_email: str, message: str) -> None:
    """
    Audit finding 21 -- the email half of api/services/security_alerts.py's
    real-time alerting (the other half is a Slack-compatible webhook).
    Goes to SECURITY_ALERT_EMAIL (an operator/security-team inbox), never
    to the affected end user -- this is an operational alert about a
    possible attack in progress, not an account notification. `message`
    is plain text (the same string also goes to a Slack-compatible
    webhook, which doesn't interpret HTML -- see api/services/
    security_alerts.py) and CAN embed attacker-influenced values (the
    email address typed into a login attempt, e.g.), so it's HTML-escaped
    here, as a whole, before being wrapped for this HTML email -- not the
    caller's job to pre-escape a string other channels consume as-is.
    """
    _send(to_email, subject="Security alert: failed-login spike detected", html=f"<p>{html.escape(message)}</p>")


def send_profile_changed_email(to_email: str, changed_fields: list[str]) -> None:
    """
    Audit finding 24 -- called by api/routers/account.py's update_profile()
    whenever a PATCH actually changes something (never on a no-op PATCH
    with no recognized fields present -- see that endpoint's docstring).
    changed_fields are always one of a small, fixed set of our own field
    names ("full_name", "company"), never raw user-supplied VALUES, so
    there's nothing here that needs HTML-escaping the way a User-Agent
    or email-typed-into-a-form string would.
    """
    fields = ", ".join(changed_fields)
    _send(
        to_email,
        subject="Your profile was updated",
        html=(
            f"<p>Your account profile was just updated. Changed: <strong>{fields}</strong>.</p>"
            f"<p>If this wasn't you, someone else may have access to your account -- "
            f"change your password immediately and review your active sessions.</p>"
        ),
    )


def send_preferences_changed_email(to_email: str, changed_fields: list[str]) -> None:
    """
    Audit finding 25 -- called by api/routers/account.py's
    update_preferences() whenever a PATCH actually changes locale and/or
    timezone. Lower-stakes wording than send_profile_changed_email above
    -- a changed UI language or timezone is far less likely to indicate
    a compromised account than a changed name/company, but RGPD
    transparency (Art. 12/13) still calls for telling the data subject
    any time their stored data changes, not just the security-sensitive
    subset of changes.
    """
    fields = ", ".join(changed_fields)
    _send(
        to_email,
        subject="Your account preferences were updated",
        html=(
            f"<p>Your account preferences were just updated. Changed: <strong>{fields}</strong>.</p>"
            f"<p>If this wasn't you, review your account and consider changing your password.</p>"
        ),
    )


def send_jwt_key_rotated_email(to_admin_email: str, rotated_at_iso: str, retention_days: int) -> None:
    """
    Audit finding 28 -- called by api/tasks/jwt_key_rotation.py every
    time it actually performs a rotation (never on a no-op run where the
    current key isn't due yet). Goes to JWT_KEY_ROTATION_ADMIN_EMAIL (an
    operator inbox, opt-in via that setting), never to end users -- this
    is infrastructure housekeeping, not an account-security event any
    individual user needs to see. Names the retention window explicitly
    so whoever reads this knows exactly when the PREVIOUS key stops being
    honored for already-issued tokens, not just that a rotation happened.
    """
    _send(
        to_admin_email,
        subject="JWT signing key rotated automatically",
        html=(
            f"<p>The application's JWT signing key was automatically rotated at "
            f"<strong>{html.escape(rotated_at_iso)}</strong>.</p>"
            f"<p>The previous key remains valid for verifying already-issued access "
            f"tokens for {retention_days} more day(s), then is discarded.</p>"
            f"<p>No action is required -- this is a routine, scheduled rotation "
            f"(see JWT_AUTO_ROTATION_INTERVAL_DAYS).</p>"
        ),
    )


def send_webauthn_credential_added_email(to_email: str, nickname: str) -> None:
    """
    Audit finding 26 -- called whenever a new physical key/authenticator
    is registered (api/routers/webauthn.py). Same reasoning as
    send_two_factor_enabled_email above: registration only needs a valid
    access token plus completing a browser ceremony, so this is the
    signal that would catch an attacker registering THEIR OWN key against
    a stolen session before the real owner notices anything else wrong.
    """
    _send(
        to_email,
        subject="A new security key was added to your account",
        html=(
            f"<p>A new WebAuthn security key (\"{html.escape(nickname)}\") was just "
            f"registered on your account as a second factor.</p>"
            f"<p>If you just did this yourself, no action is needed.</p>"
            f"<p>If you did NOT do this, someone else may have access to your "
            f"account. Remove the key you don't recognize from your account "
            f"security settings, then change your password immediately.</p>"
        ),
    )


def send_webauthn_credential_removed_email(to_email: str, nickname: str) -> None:
    """The flip side of send_webauthn_credential_added_email above --
    called by api/routers/webauthn.py whenever a registered key is
    removed, so the real owner notices if it wasn't them (e.g. an
    attacker clearing out a key they can't use, to force a fallback to a
    factor they DO control)."""
    _send(
        to_email,
        subject="A security key was removed from your account",
        html=(
            f"<p>The WebAuthn security key \"{html.escape(nickname)}\" was just "
            f"removed from your account.</p>"
            f"<p>If you just did this yourself, no action is needed.</p>"
            f"<p>If you did NOT do this, review your account's remaining "
            f"security keys and consider changing your password.</p>"
        ),
    )


def send_enterprise_sso_connection_created_email(to_admin_email: str, email_domain: str, display_name: str) -> None:
    """
    Audit finding 27 -- called by api/routers/enterprise_sso.py whenever
    an admin configures a new enterprise IdP connection. Every future
    user whose email matches email_domain will be able to sign in through
    that IdP without a password on this app at all -- a real access-control
    change, worth a notification even though the action itself already
    required an authenticated admin, the same way audit finding 19/20's
    security-alert emails exist despite already gating on require_admin.
    """
    _send(
        to_admin_email,
        subject=f"Enterprise SSO connection configured for {email_domain}",
        html=(
            f"<p>A new enterprise SSO connection (\"{html.escape(display_name)}\") was just "
            f"configured for the email domain <strong>{html.escape(email_domain)}</strong>.</p>"
            f"<p>From now on, accounts with an email address at that domain can sign in "
            f"through this identity provider.</p>"
            f"<p>If you didn't just do this, review Admin > SSO Connections immediately.</p>"
        ),
    )


def send_organization_member_added_email(to_email: str, organization_name: str, role: str) -> None:
    """Etape 1.2.3 -- called by api/routers/organization_members.py's
    invite_organization_member() every time an Admin or Owner adds an
    EXISTING account to their organization immediately, no acceptance
    step. Partie 1.3.4's api/routers/invitations.py reuses this SAME
    function as its own "invitation accepted" confirmation -- from the
    recipient's point of view the outcome is identical ("you're now a
    member of X, with role Y"), whether they were added directly or
    accepted an emailed invitation link."""
    _send(
        to_email,
        subject=f"You've been added to {organization_name}",
        html=(
            f"<p>You were just added to the organization <strong>{html.escape(organization_name)}</strong> "
            f"as <strong>{html.escape(role)}</strong>.</p>"
            f"<p>If you don't recognize this organization, contact its administrator or reply to this email.</p>"
        ),
    )


def send_organization_invitation_email(to_email: str, organization_name: str, role: str, invite_link: str) -> None:
    """Partie 1.3.4 -- called by api/routers/invitations.py whenever an
    invitation is created (or re-issued, see create_or_reissue_invitation).
    Unlike send_organization_member_added_email above, the recipient is
    NOT a member yet -- `invite_link` embeds the raw (not hashed) token,
    same "email the raw value, store only its hash" convention as
    api/services/password_reset.py's reset link."""
    _send(
        to_email,
        subject=f"You've been invited to join {organization_name}",
        html=(
            f"<p>You've been invited to join <strong>{html.escape(organization_name)}</strong> "
            f"as <strong>{html.escape(role)}</strong>.</p>"
            f"<p>Click the link below to accept. It expires in {settings.INVITATION_EXPIRE_DAYS} days.</p>"
            f'<p><a href="{invite_link}">{invite_link}</a></p>'
            f"<p>If you don't recognize this organization, you can safely ignore this email.</p>"
        ),
    )


def send_organization_member_role_changed_email(to_email: str, organization_name: str, new_role: str) -> None:
    """The flip side of a role change -- lets the affected member notice
    if it wasn't something they expected (a stolen admin session
    quietly demoting or promoting someone would otherwise be silent)."""
    _send(
        to_email,
        subject=f"Your role in {organization_name} was changed",
        html=(
            f"<p>Your role in <strong>{html.escape(organization_name)}</strong> was just changed to "
            f"<strong>{html.escape(new_role)}</strong>.</p>"
            f"<p>If you didn't expect this, contact your organization's administrator.</p>"
        ),
    )


def send_organization_member_removed_email(to_email: str, organization_name: str) -> None:
    _send(
        to_email,
        subject=f"You were removed from {organization_name}",
        html=(
            f"<p>You were just removed from the organization <strong>{html.escape(organization_name)}</strong>.</p>"
            f"<p>If you believe this was a mistake, contact your organization's administrator.</p>"
        ),
    )


def send_invoice_email(to_email: str, invoice_number: str, total_display: str, organization_name: str) -> None:
    """Partie 12.4 -- notifies that a real invoice is ready. Deliberately
    does not attach the PDF inline (Resend's REST API supports
    attachments, but keeping this consistent with every other
    notification-only email here means the recipient always fetches the
    real, current PDF via GET /organizations/{id}/billing/invoices/{id}/pdf
    rather than trusting a copy that could go stale)."""
    subject = f"Invoice {invoice_number} for {organization_name}"
    _send(to_email, subject, f"<p>Your invoice <strong>{html.escape(invoice_number)}</strong> ({html.escape(total_display)}) is ready. Sign in to your billing dashboard to view or download it.</p>")


def send_invoice_reminder_email(to_email: str, invoice_number: str, total_display: str, days_overdue: int) -> None:
    subject = f"Reminder: invoice {invoice_number} is overdue"
    _send(to_email, subject, f"<p>Invoice <strong>{html.escape(invoice_number)}</strong> ({html.escape(total_display)}) is now {days_overdue} day(s) overdue. Please arrange payment.</p>")


def send_usage_limit_warning_email(to_email: str, organization_name: str, resource_type: str, current_percent: int, limit: int) -> None:
    """Partie 18 -- the email half of api/tasks/sales.py's
    check_usage_limits sweep. Same "notify, don't fabricate an
    enforcement action" pattern as send_invoice_reminder_email:
    the actual hard block already happens at request time
    (api/services/billing_usage.py's check_limits), this is a
    heads-up before that point is reached."""
    subject = f"{organization_name} is at {current_percent}% of its {resource_type} limit"
    _send(
        to_email, subject,
        f"<p>Your organization <strong>{html.escape(organization_name)}</strong> is using "
        f"{current_percent}% of its plan's {html.escape(resource_type)} limit ({html.escape(str(limit))} total). "
        f"Consider upgrading your plan before you hit it.</p>",
    )


def send_analytics_report_email(to_email: str, total_events_last_30d: int) -> None:
    """Partie 20 -- the email half of api/tasks/analytics.py's
    send_analytics_report. A real, current count, not a canned figure."""
    subject = "Your monthly analytics report"
    _send(
        to_email, subject,
        f"<p>Your organization tracked <strong>{total_events_last_30d}</strong> product events in the last 30 days. "
        f"Sign in to your analytics dashboard for the full breakdown.</p>",
    )


def send_ab_test_report_email(to_email: str, test_name: str, status: str, metrics: dict) -> None:
    """Partie 21 -- the email half of api/tasks/ab_tests.py's
    send_ab_test_report. Real, current status -- not a canned string."""
    subject = f"A/B test report: {test_name}"
    tracked_metrics = ", ".join(sorted(set(metrics.get("a", {})) | set(metrics.get("b", {})))) or "none tracked yet"
    _send(
        to_email, subject,
        f"<p>Your A/B test <strong>{html.escape(test_name)}</strong> is currently <strong>{html.escape(status)}</strong>. "
        f"Tracked metrics: {html.escape(tracked_metrics)}. Sign in to your dashboard for the full statistics.</p>",
    )


def send_via_custom_email_domain(domain_row: CustomDomain, from_local_part: str, to_email: str, subject: str, html_body: str) -> None:
    """
    Partie 1.4.5, item 6's literal "l'envoi d'email avec un domaine
    personnalisé fonctionne" -- a real send through this SAME Resend
    /emails endpoint, using f"{from_local_part}@{domain_row.domain}"
    (e.g. contact@ma-boite.com) instead of settings.EMAIL_FROM_ADDRESS.

    Requires domain_row.email_verified (this app's OWN ownership check,
    api/security/email_domains.py's verify_email_domain) -- but passing
    that check alone does NOT guarantee Resend accepts the send: Resend
    independently requires ITS OWN domain object
    (api/services/resend_domains.py) to have reached status "verified"
    too, which needs that domain's real MX/SPF/DKIM records (under
    Resend's own naming, NOT this app's self-generated DKIM -- see
    api/security/email_domains.py's module docstring) to actually be
    published. A domain that passes our ownership check but was never
    completed with Resend will be rejected by Resend's real API with a
    real error, surfaced here as RuntimeError like every other _send
    failure -- never swallowed, never faked as a successful send.
    """
    if not domain_row.email_verified:
        raise ValueError(f"'{domain_row.domain}' has not completed ownership verification for email yet -- call verify_email_domain first")
    _send(to_email, subject, html_body, from_address=f"{from_local_part}@{domain_row.domain}")
