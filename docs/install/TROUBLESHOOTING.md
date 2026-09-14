# Troubleshooting

## `install.sh` exits immediately after creating `.env`

Expected on first run — it stops so you can fill in `DATABASE_URL`,
`RESEND_API_KEY`, and a license key before continuing. Re-run
`./install.sh` once `.env` is filled in. See
[Environment Variables](ENVIRONMENT.md).

## Migrations fail on startup

Check `DATABASE_URL` uses the `asyncpg` driver
(`postgresql+asyncpg://...`), not plain `postgresql://` — a common
copy-paste mistake from a generic Postgres connection string. See
[Database Setup](DATABASE_SETUP.md).

## Frontend can't reach the API (CORS errors)

The frontend's CORS origin variable in `.env` must match the port your
frontend actually runs on. See the "Frontend / CORS" section of
[Environment Variables](ENVIRONMENT.md).

## Fine-tuning jobs fail immediately for Anthropic

Expected — Anthropic has no public fine-tuning API. Use OpenAI or
Mistral instead. See
[`docs/fine-tuning/OVERVIEW.md`](../fine-tuning/OVERVIEW.md).

## Custom domain SSL stuck "pending"

The DNS-01 TXT record likely hasn't propagated yet, or wasn't created
correctly. See [SSL & Domains](SSL_AND_DOMAINS.md) — this step is
manual, not automatic.

## `celery-beat` running scheduled tasks twice

You likely have more than one `celery-beat` instance running. It must
run as exactly one instance — see [Scaling](SCALING.md).

## Still stuck

Check `docker compose -f docker-compose.selfhosted.yml logs -f api` for
the actual error, and see [Observability Stack](OBSERVABILITY_STACK.md)
if you have monitoring configured.
