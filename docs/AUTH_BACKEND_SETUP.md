# Running api/ locally

The auth backend (Partie 1.1) needs several real services configured to
exercise every feature end-to-end. This documents what's needed and how
to run each layer -- see `.env.example` for the full variable list with
inline comments; nothing here duplicates the actual values (never commit
real secrets, including into this file).

## Required for the API to start at all

- **PostgreSQL** (`DATABASE_URL`, `postgresql+asyncpg://...`) -- any
  Postgres works; Supabase's free tier is what this was built and tested
  against. Its direct connection (`db.<ref>.supabase.co`) is IPv6-only
  unless you pay for the IPv4 add-on -- use the **Session pooler**
  connection string instead (`aws-<n>-<region>.pooler.supabase.com:5432`,
  username `postgres.<project-ref>`) if you're on an IPv4-only network.
  Run migrations once: `python -m alembic upgrade head`.
- `JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET` -- generate both with
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Start the server: `uvicorn api.main:app --reload`, then `http://localhost:8000/docs`.

**The server reads `.env` once at startup** -- restart it after changing
any environment variable, `--reload` only watches `.py` files.

## Optional layers, and what breaks without them

Every layer below fails gracefully if unconfigured (a clear error, not a
crash) -- the API stays usable for everything that doesn't need it.

### Resend (1.1.3 password reset, 1.1.4 email verification)

`RESEND_API_KEY` from resend.com/api-keys. Until your own sending domain
shows "Verified" under resend.com/domains, Resend's sandbox sender
(`onboarding@resend.dev`, the default in `.env.example`) only delivers to
*your own* Resend account email -- fine for solo dev/testing, not for
real users. Verify a domain (DNS records shown in the Resend dashboard)
and switch `EMAIL_FROM_ADDRESS` to that domain for real recipients.

Without a key configured: registration/reset/OTP requests still succeed
(HTTP-wise), the email send is skipped with a logged warning.

### Google / GitHub OAuth (1.1.5, 1.1.6)

Create credentials at Google Cloud Console (OAuth client, type "Web
application") and github.com/settings/developers ("New OAuth App"). In
both, the redirect URI must be exactly:
`{OAUTH_REDIRECT_BASE_URL}/auth/oauth/{provider}/callback`
(e.g. `http://localhost:8000/auth/oauth/google/callback`) -- a mismatch
here is the #1 cause of `redirect_uri_mismatch` errors.

Set `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET` and/or
`GITHUB_OAUTH_CLIENT_ID`/`GITHUB_OAUTH_CLIENT_SECRET`. A provider with
either half unset is simply not registered -- its `/authorize` route
returns 503 instead of crashing the app.

Manual verification (no way to automate a real provider's consent screen):
open `http://localhost:8000/auth/oauth/google/authorize` (or `github`) in
a browser, sign in, approve -- you land on `{FRONTEND_URL}/oauth-callback`
(404 is expected with no frontend yet) with `#access_token=...` in the
URL fragment if it worked.

**2FA-enabled accounts get `#mfa_required=true&mfa_token=...` instead** --
Google/GitHub proving who the user is does not satisfy this app's own
2FA requirement (it's a separate credential the provider knows nothing
about), so the callback routes through the same MFA hand-off as a
password login: the frontend must follow up with `POST /auth/2fa/verify-login`
using that `mfa_token`, exactly as it would after `/auth/login` returns
`MFARequiredResponse`. Unlike the consent screen itself, this branch
*is* covered by the automated suite (`test_oauth_callback_requires_2fa_when_the_account_has_it_enabled`)
by faking the token-exchange step, not the browser.

### 2FA recovery codes (1.1.7)

`POST /auth/2fa/enable` (and later `POST /auth/2fa/recovery-codes/regenerate`)
returns 10 single-use codes in plaintext, exactly once -- only their
SHA-256 hash is stored. Alongside the JSON `recovery_codes` list, the
same response also includes `recovery_codes_file`: a ready-to-download
`data:text/plain;base64,...` URI with the same codes, meant for
`<a download="recovery-codes.txt" href="{recovery_codes_file}">` --
same technique `/auth/2fa/setup`'s `qr_code_data_uri` already uses for
the QR `<img>`, so there's no separate "fetch the codes again" endpoint
that would undermine "shown exactly once."

They're the fallback for `POST /auth/2fa/verify-login` when the
authenticator device itself is lost: `POST /auth/2fa/verify-recovery-code`
takes the same `mfa_token` from `/auth/login` plus one recovery code
instead of a 6-digit TOTP code. Disabling 2FA (`POST /auth/2fa/disable`)
deletes any unused codes, and consuming one always emails the account a
"a recovery code was used" notice. Unlike TOTP itself, this whole flow is
fully covered by the automated suite -- no physical device involved.

**Every state change here is notified by email**, not just consuming a
code: enabling 2FA, disabling it, and regenerating recovery codes all
send one. Enabling is the highest-stakes case -- `/setup` hands the TOTP
secret back in plaintext (as the QR code) to anyone holding a valid
access token, and `/enable` only needs a code derived from that same
secret, so a stolen token alone could let an attacker turn 2FA on under
a secret only THEY control and lock the real owner out. Disabling and
regenerating both already require a valid *current* TOTP code to reach
(a much stronger bar), but get the same treatment anyway: a stolen
unlocked device with the authenticator app already open could still
pass that check, and both actions are exactly what someone in that
position would use to cut off the real owner's own fallback.

**Lost the device AND all 10 codes:** `POST /auth/2fa/lockout-recovery/request`
(email + password) starts a last-resort removal of 2FA that only becomes
confirmable (`POST /auth/2fa/lockout-recovery/confirm`) after
`TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS` (default 24h) -- the same
"we'll do this in N hours unless you stop us" pattern GitHub/Google use.
Logging in normally with the authenticator or a recovery code in the
meantime cancels any pending request automatically, so a compromised
mailbox + leaked password alone can't silently wipe 2FA while the real
owner is still actively using the account.

**Running low on codes:** `GET /auth/2fa/recovery-codes/status` returns
`{"total": 10, "remaining": N}` (counts only, never the codes themselves)
so the frontend can prompt "regenerate your codes" before the user is
down to zero, instead of them finding out only when `/verify-recovery-code`
starts failing.

**Adding a password as a fallback (OAuth-only accounts):** `POST /account/set-password`
(authenticated) lets a Google/GitHub-only account (`hashed_password` is
`None`) set one. Without this, losing access to the linked provider --
disabled account, revoked access, provider outage -- would mean losing
access to this app too, with no way back in at all. Rejected with 400 if
the account already has a password (use `/auth/password/forgot` to
change an existing one instead).

### S3-compatible storage (1.1.13 avatar upload)

Any S3-compatible bucket: AWS S3, Cloudflare R2 (needs a payment method
on file even for free-tier usage), or **Supabase Storage's own S3 API**
(no card needed, same project as `DATABASE_URL` --
Storage → create a bucket dedicated to avatars → Configuration → S3 →
New access key). `S3_BUCKET_NAME` must be a bucket dedicated to avatars:
the object key has no extra prefix of its own, so a shared bucket would
collide with other uploads.

Uploaded files are validated against their actual magic bytes (the real
leading signature of a PNG/JPEG/WEBP file), not the Content-Type header
the client declared -- see `_detect_image_content_type()` in
`api/services/storage.py`. Account purge (1.1.10) also deletes the
avatar object from the bucket, not just the database row, so a
hard-deleted account doesn't leave storage orphaned.

### RGPD consent withdrawal and account restore (1.1.10, 1.1.12)

`POST /account/consent/withdraw` (authenticated) deactivates the account
and revokes every session immediately, but -- unlike `DELETE /account/me`
-- schedules no purge: withdrawing consent (RGPD Art. 7(3)/21) and asking
for erasure (Art. 17) are different rights with different consequences
here.

`DELETE /account/me` itself is undoable during its `ACCOUNT_PURGE_DELAY_DAYS`
grace window: `POST /account/restore/request` (public, `{"email": "..."}`,
same silent/generic response either way as `/auth/password/forgot`) emails
a link if that account is still within its grace period; `POST /account/restore/confirm`
(`{"token": "..."}`) reactivates it. Restoring does not log the user in --
it clears `deleted_at`/`deletion_scheduled_at` and they log in normally
afterward, same as a password reset.

**Consent withdrawal is undoable too, on purpose:** `POST /account/consent/reactivate/request`
(public, same silent/generic shape as the two above) + `POST /account/consent/reactivate/confirm`
(`{"token": "...", "accept_terms": true}`) reverses `/account/consent/withdraw`
-- `accept_terms` must be `true`, since consent has to be freely given
again, not silently restored to whatever it was before. This is
deliberately a separate flow from `/account/restore/*`: it only applies
to a consent-withdrawn account, never to one that's also fully deleted
(`is_deleted`) -- undoing a deletion is `/account/restore/*`'s job, not
this one's.

**Two warnings before permanent deletion, not one (4.6):**
`DELETE /account/me` sends an immediate confirmation email the moment
deletion is requested; a separate Celery task
(`api/tasks/account_deletion_reminder.py`, same daily-beat pattern as
account purge) sends a second, closer-to-the-deadline reminder once
`deletion_scheduled_at` falls within `ACCOUNT_DELETION_REMINDER_DAYS_BEFORE`
(default 3 days) -- a single email 30 days out is easy to forget by the
time it actually matters. Sent once per deletion cycle
(`User.deletion_reminder_sent_at`), cleared by
`POST /account/restore/confirm` so a later deletion is eligible for its
own fresh reminder.

### Forced re-consent when TERMS_VERSION changes (4.3)

`get_current_user` (`api/dependencies.py`) blocks a request with 403 if
`user.terms_version != settings.TERMS_VERSION` -- an account that
consented under an older version of the terms can't keep using the
service until it re-consents via `POST /account/consent/accept-updated-terms`
(`{"accept_terms": true}`).

**Not every route is behind this gate.** A small, deliberate set uses
`get_current_user_any_consent_status` instead (identity/active/blacklist
checks only, no terms-freshness check), because these can't be
conditioned on accepting NEW terms first without violating the very
rights they exist to serve: `GET /account/export` (RGPD Art. 15/20),
`DELETE /account/me` (Art. 17), `POST /account/consent/withdraw`
(Art. 7(3)/21), `GET`/`DELETE /sessions*` (basic account security --
you must always be able to see or kill your own sessions),
`POST /auth/2fa/setup`, `/enable`, `/disable`, `/recovery-codes/regenerate`,
and `GET /recovery-codes/status` (same reasoning as sessions -- each
already requires either no prior 2FA state or a valid current TOTP code,
so turning 2FA on/off or rotating recovery codes is basic account
security, not "ordinary use" that can wait on a new-terms prompt),
`GET /account/me` (so a frontend has something to show the "please
accept updated terms" prompt with), and
`POST /account/consent/accept-updated-terms` itself (it obviously can't
require the problem it fixes to already be fixed).

### "New sign-in" notifications (1.1.8, 1.1.9)

Every session-issuing endpoint (login, refresh, the OAuth callback,
2FA verify-login/verify-recovery-code) emails the account when a login
looks new. "New" requires BOTH the User-Agent AND the IP address to be
unrecognized together, not the User-Agent alone -- a stolen refresh
token replayed from a different network still triggers the email even
if the attacker sends a matching User-Agent string. Known, accepted
limitation: both signals are still just headers (attacker-influenceable
in principle), and a legitimate user roaming between networks will see
more of these emails than a User-Agent-only check would produce -- an
intentional trade favoring not missing a real hijack over minimizing
false positives. See `api/security/sessions.py`'s `issue_session()`
docstring.

### Access token revocation (1.1.15)

An access token is normally a stateless JWT -- valid until it expires,
nothing the server can do about it before then. `revoked_access_tokens`
(a real table, not Redis -- these rows need to survive as reliably as
the rest of this app's security-relevant data) is what makes it
revocable: every access token carries a `jti`, stored on the `Session`
row it's paired with, and `GET/POST` `Depends(get_current_user)` checks
that `jti` against this table on every request.

**Every place that already revoked a session now blacklists its access
token too** -- logout, refresh rotation (the pre-rotation token), a
specific "log out that device" call, and every "kill every session"
action: password reset, account deletion, consent withdrawal, 2FA
disable, 2FA lockout-recovery. This is `revoke_session()` /
`revoke_all_sessions_for_user()` (`api/security/sessions.py`), not
something each caller does separately -- a stolen access token dies
the moment ANY of those happen, not just at its own natural ~15-minute
expiry.

Cost: one extra indexed DB read on every authenticated request (see
`get_current_user`'s docstring in `api/dependencies.py`). Housekeeping:
`api/tasks/token_blacklist_cleanup.py` (same Celery Beat schedule as
account purge, offset by 15 minutes) deletes blacklist rows once their
underlying token would have expired anyway, so the table doesn't grow
forever.

### JWT key rotation (1.1.15)

`JWT_PREVIOUS_SECRET_KEYS` (comma-separated) holds keys still accepted
when *verifying* a token, never used to *sign* a new one. Two different
procedures, same mechanism:

- **Routine rotation**: generate a new `JWT_SECRET_KEY`, move the OLD
  value into `JWT_PREVIOUS_SECRET_KEYS`, redeploy. Already-issued access
  tokens keep working (verified against the previous key) until they
  naturally expire; remove the old key from the list once
  `ACCESS_TOKEN_EXPIRE_MINUTES` has comfortably passed.
- **Responding to a leak**: generate a new `JWT_SECRET_KEY` and leave
  `JWT_PREVIOUS_SECRET_KEYS` empty (do NOT list the leaked key). Every
  access token signed with the leaked key fails to verify immediately --
  correct, since a leaked signing key means an attacker could have
  forged arbitrary tokens for any user, so nothing signed with it can be
  trusted anymore. Refresh tokens are unaffected (random opaque values,
  hashed in the database, not JWTs), so real users get a fresh,
  correctly-signed access token via `POST /auth/refresh` without needing
  to log in again -- only actually-forged/stolen tokens die.

### CSRF protection on /auth/refresh and /auth/logout (1.1.16)

These are the only two endpoints that authenticate purely off a cookie,
no `Authorization` header required -- every other protected route needs
a Bearer token a cross-site attacker's forged request can't produce.
Double-submit: `issue_session()` sets a second, JS-readable `csrf_token`
cookie alongside the httpOnly refresh cookie; both routes require an
`X-CSRF-Token` header matching it (`api/security/csrf.py`). A frontend
reads `document.cookie` for `csrf_token` and echoes it back on every
call to these two endpoints. SameSite=lax on the refresh cookie already
blocks most cross-site cookie-riding in modern browsers -- this is
defense-in-depth on top of that, not a replacement for it.

### Redis + Celery (1.1.10 account purge, J+30)

Needs a real Redis reachable at `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`.

- Docker: `docker run -p 6379:6379 redis`
- Windows without Docker/admin rights: `winget install
  taizod1024.redis-windows-fork`, then run the extracted
  `redis-server.exe` directly (no service install needed)
- Anywhere else: any managed Redis works

Worker: `python -m celery -A api.tasks.celery_app worker --loglevel=info --pool=solo`
(`--pool=solo` is required on Windows -- prefork uses `os.fork()`, not
available there; drop the flag elsewhere).

Beat (the daily 03:00 UTC scheduler that actually triggers the sweep in
production): `python -m celery -A api.tasks.celery_app beat --loglevel=info`

Without Beat running, the purge task exists and works (verified,
see below) but nothing calls it on a schedule -- trigger it manually for
testing: `python -c "from api.tasks.account_purge import purge_deleted_accounts; print(purge_deleted_accounts.delay().get())"`

Same for the token-blacklist cleanup (1.1.15):
`python -c "from api.tasks.token_blacklist_cleanup import purge_expired_blacklist_entries; print(purge_expired_blacklist_entries.delay().get())"`

And the pre-purge deletion reminder (4.6):
`python -c "from api.tasks.account_deletion_reminder import send_pending_deletion_reminders; print(send_pending_deletion_reminders.delay().get())"`

### Rate limiting (brute-force / spam protection)

Uses the same Redis as Celery above, on its own DB number
(`RATE_LIMIT_REDIS_URL`, default DB 2) so the two never share keys.
Enforced on the 5 endpoints an attacker would actually target:

| Endpoint | Limit | Keyed by |
|---|---|---|
| `POST /auth/login` | 5 / 15 min | IP **and** target email (either blocks) |
| `POST /auth/register` | 3 / 60 min | IP |
| `POST /auth/password/forgot` | 3 / 60 min | target email |
| `POST /auth/verify-email/request` | 3 / 60 min | account email |
| `POST /auth/2fa/verify-login` | 5 / 15 min | the mfa_token itself (hashed) |
| `POST /auth/2fa/verify-recovery-code` | 5 / 15 min | the mfa_token itself (hashed), own counter from verify-login |
| `POST /auth/2fa/enable`, `/disable`, `/recovery-codes/regenerate` | 5 / 15 min | user id -- shared counter across all three, so a stolen access token can't brute-force the TOTP code by spreading guesses across endpoints |
| `POST /auth/2fa/lockout-recovery/request` | 5 / 15 min | IP **and** target email (checks a password guess, same thresholds as `/auth/login`) |
| `POST /account/restore/request` | 3 / 60 min | target email |
| `POST /account/consent/reactivate/request` | 3 / 60 min | target email |

If `RATE_LIMIT_REDIS_URL` is unreachable, enforcement fails **open**
(logs a warning, lets the request through) rather than blocking all
auth traffic -- see `api/security/rate_limit.py`'s docstring for why
that's the deliberate choice, not an oversight. `RATE_LIMIT_ENABLED=False`
disables it outright for local dev without Redis; never set that in a
real deployment.

**This trade-off is only "deliberate," not "silent," if it's visible:**
`GET /health/ready` actually reaches Postgres and the rate-limiting Redis
and reports `{"database": "ok"|"unreachable", "rate_limit_redis": "ok"|"unreachable -- rate limiting is NOT currently enforced"}`
(always HTTP 200 -- the body is what's actionable, not the status code,
so a degraded rate limiter doesn't get treated as "take this instance
down" by infrastructure that only reads status codes). Point an uptime
monitor or dashboard at it, not just at `/health` (the plain liveness
check, which deliberately touches nothing).

**Not implemented: CAPTCHA on registration.** Left out deliberately for
now -- it needs a third-party account (reCAPTCHA/hCaptcha/Turnstile) and
was marked optional in the spec this was built against. The rate limit
on `/auth/register` (3/hour/IP) already blocks the same automated-signup-spam
threat CAPTCHA targets, just with a coarser IP-based signal instead of a
bot-detection heuristic. Straightforward to add later if mass registration
from many distinct IPs becomes a real problem CAPTCHA would catch and
rate limiting wouldn't.

## Tests

```bash
# Fast unit tests -- in-memory SQLite, no external services, always run
pytest tests/test_auth_security.py tests/test_auth_api.py

# Integration tests -- need real services, skip cleanly if unreachable
pytest tests/test_postgres_integration.py         # needs DATABASE_URL
pytest tests/test_celery_integration.py           # needs DATABASE_URL (runs task logic via .apply(), no worker needed)
pytest tests/test_avatar_storage_integration.py   # needs DATABASE_URL + S3_*
pytest tests/test_oauth_logic_integration.py      # needs DATABASE_URL
pytest tests/test_rate_limiting_integration.py    # needs DATABASE_URL + RATE_LIMIT_REDIS_URL
pytest tests/test_e2e_lifecycle.py                # needs DATABASE_URL + S3_* + a LIVE Celery worker (see above)

# Everything
pytest tests/
```

`test_e2e_lifecycle.py` runs the full register → verify → login → enable
2FA → logout → login-with-2FA → update profile/preferences → upload
avatar → list/revoke sessions → reset password → soft-delete → purge
sequence against real infrastructure end to end -- it's the slowest test
in the suite (~70s) because several steps genuinely round-trip to
Supabase, S3, and a live Celery worker rather than mocking any of them.

## What is NOT automated, and why

- **OAuth consent flows** -- clicking "Allow" on Google's/GitHub's actual
  consent screen needs a human in a real browser session; there's no
  automatable substitute that would still be testing the real thing.
- **2FA with a physical authenticator app** -- the test suite verifies
  the TOTP logic itself (same algorithm, same secret format any real app
  implements) via `pyotp` computing codes directly from the issued
  secret, which is a legitimate test of the logic but not proof a real
  phone's camera can scan the generated QR code and that app produces
  matching codes. Verify manually once: `POST /auth/2fa/setup`, decode
  the returned `qr_code_data_uri`, scan it with Google Authenticator (or
  any TOTP app), confirm `POST /auth/2fa/enable` accepts the phone's code.
