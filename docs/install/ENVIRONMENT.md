# Environment Variables

The authoritative reference is [`.env.example`](../../.env.example)
itself (482 lines, organized by feature area with inline comments) —
copy it to `.env` and fill in. This page is a category-level map so you
know where to look.

```bash
cp .env.example .env
```

## Required to start

- **Database** — `DATABASE_URL` (must use the `asyncpg` driver:
  `postgresql+asyncpg://...`, not plain `postgresql://`).
- **JWT / sessions** — `JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`,
  `AUDIT_LOG_HMAC_SECRET_KEY` (deliberately a separate key from the
  other two — see `.env.example`'s comment on key separation for audit
  log tamper-evidence). Generate each with:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
  `./install.sh` generates `SESSION_MIDDLEWARE_SECRET` for you
  automatically on first run.

## By category

- **Auth & sessions** — JWT rotation (`JWT_PREVIOUS_SECRET_KEYS`),
  password reset / email OTP, 2FA lockout recovery, session idle
  timeout, concurrent session limits, password policy. See
  [`docs/AUTH_BACKEND_SETUP.md`](../AUTH_BACKEND_SETUP.md).
- **Frontend / CORS** — the frontend's dev origin, must match your
  actual frontend port.
- **OAuth** — one provider key pair per supported provider; leave a
  pair unset to disable that provider.
- **Email** — Resend (`RESEND_API_KEY`) for transactional email.
- **Object storage** — S3-compatible credentials, used for avatars,
  documents, media, and fine-tuning datasets.
- **Document import connectors** — GitHub, Google Drive, Google
  Docs/Sheets/Slides, Notion, Confluence, OneDrive, ZIP archive, batch
  upload — each with its own credential block.
- **Voice** — recording upload storage and voice provider keys, plus
  Twilio for telephony.
- **Celery / rate limiting** — broker URL, account-purge sweep
  schedule, brute-force/spam rate limits, geo-adaptive rate limiting,
  trusted IP exemptions.
- **Encryption** — shared encryption-at-rest key for DB-stored secrets
  (`api/security/encryption.py`), including where the SSL/ACME account
  is stored.
- **SSL automation** — Let's Encrypt / ACME settings for custom domains
  (DNS-01) — see [SSL & Domains](SSL_AND_DOMAINS.md).
- **WebAuthn** — `rp_id` must be the exact domain (no scheme/port) your
  frontend is served from.
- **Monitoring** — Grafana Cloud (Loki/Tempo) and Datadog LLM
  Observability, both optional — see
  [Observability Stack](OBSERVABILITY_STACK.md).
- **Airbyte / n8n** — self-hosted automation platform connection
  settings — see [Integrations](../developer/INTEGRATIONS.md).
- **Self-hosted deployment** — variables specific to
  `docker-compose.selfhosted.yml` / `install.sh`.
- **RAG pipeline (`src/`, `dashboard/`)** — `ANTHROPIC_API_KEY` and,
  optionally, the Google Calendar/Sheets service-account variables for
  the original single-tenant demo's agentic tools — see
  [`src/README.md`](../../src/README.md#phase-02-setup-google-calendar--sheets).

## Never commit `.env`

`.env` is gitignored. Only `.env.example` (with placeholder values) is
committed.
