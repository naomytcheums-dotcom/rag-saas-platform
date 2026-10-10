# Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| Every request hangs or times out right after a deploy (Render free plan) | 512 MB is not enough for gunicorn plus the ML libraries; a worker in the same container makes it worse | Run the API alone on the free plan, or move to a paid plan; run the Celery worker as a separate service (`deploy/render/render.api.yaml`). |
| Documents stay `pending` forever | No Celery worker is running, or Redis is unreachable | Start a worker (`celery -A api.tasks.celery_app worker`), check `REDIS_URL`, then `POST /documents/{id}/reindex`. |
| Periodic jobs never run (renewals, purges, scheduled reindex) | No Celery beat, or two beats | Run exactly one `celery ... beat`. |
| `GET /organizations/{id}/notifications/templates` answers 500 | Migration 0136 not applied | Back up, then `alembic upgrade head` on the production database. |
| Evaluation split / escalation endpoints answer 500 | Migrations 0137 / 0138 not applied | Same as above. |
| Login works but the dashboard shows 401 after a few minutes | Access token expired and the refresh cookie is blocked | Check `COOKIE_SECURE`, the `FRONTEND_URL` / CORS origin and that the API and the site share a registrable domain, or use the token flow. |
| "Insufficient AI credits" in chat | The organization has no credits and no own provider key | Buy a credit pack, or configure the organization's own LLM key (Settings > LLM). |
| 429 on many requests | Rate limit; without Redis the limit is per process | Provide `REDIS_URL`; raise the organization's limits. |
| `/metrics` answers 401 | `METRICS_AUTH_TOKEN` is set | Send `Authorization: Bearer <token>`. If the variable is not set, `/metrics` is public: set it. |
| Google/GitHub sign-in button missing | `NEXT_PUBLIC_OAUTH_PROVIDERS` not set on the frontend | Set `google,github` (only providers whose credentials are configured on the API). |
| OAuth sign-in ends on a 503 page | The API has no client id/secret for that provider | Set `OAUTH_GOOGLE_*` / `OAUTH_GITHUB_*` on the API. |
| Verification e-mail never arrives | `RESEND_API_KEY` missing, or a sender domain that is not verified | Set the key; verify the sender domain in Resend. |
| Webhook deliveries fail | Target URL blocked by the SSRF guard (private address) or not HTTPS | Use a public HTTPS URL; check the delivery log. |
| Chat answers "I do not know" too often | Retrieval returns nothing above the score threshold | Lower the organization's score threshold, check that documents are `ready`, run the Eval Lab on a held-out split. |
| Local preview shows production data | The preview server was started with the production `.env` | Use `scripts/dev_isolated_server.py`; it refuses to start if any URL is not local. |

If none of this matches, collect the request id (`X-Request-ID` response header), the time, and the Sentry event id, and look in the audit log (`GET /admin/audit-logs`).
