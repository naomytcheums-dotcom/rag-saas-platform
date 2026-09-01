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

If `RATE_LIMIT_REDIS_URL` is unreachable, enforcement fails **open**
(logs a warning, lets the request through) rather than blocking all
auth traffic -- see `api/security/rate_limit.py`'s docstring for why
that's the deliberate choice, not an oversight. `RATE_LIMIT_ENABLED=False`
disables it outright for local dev without Redis; never set that in a
real deployment.

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
