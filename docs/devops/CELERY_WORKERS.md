# Celery: workers, scheduler and deployment

Prepared 2026-10-10 from the code (`api/tasks/celery_app.py`, `Dockerfile.api`, `docker-entrypoint.sh`, `render.yaml`,
`.github/workflows/celery-worker.yml`). **Nothing described here has been deployed or created on any host**: it is a proposal. Whether a
worker or a beat currently runs in production is **not verifiable from the repository** (BLOCKED_EXTERNAL).

## What the code does today
- 105 registered tasks (`audit-reports/remediation-2026-10-10/celery-task-inventory.csv`), 61 beat entries, all pointing to registered tasks
  (`tests/test_celery_safety_config.py`). One queue (`celery`). Retries: only Celery's default (`max_retries=3`, used only when a task calls
  `retry`); 2 tasks set 5. `acks_late` is off (a task lost with its worker is not redelivered).
- Before this change **no task had any time limit** and workers prefetched 4 tasks each. Now: soft 3 300 s / hard 3 600 s for every task
  (`CELERY_TASK_SOFT_TIME_LIMIT_SECONDS`, `CELERY_TASK_TIME_LIMIT_SECONDS`, `0` disables) and prefetch 1 (`CELERY_WORKER_PREFETCH_MULTIPLIER`).
  The hard limit is not enforced by the `solo` pool.
- `Dockerfile.api` starts **gunicorn only**. `docker-entrypoint.sh` can start a worker next to gunicorn but is not used: that experiment made the
  512 MB free container unresponsive (comment in `Dockerfile.api`). `render.yaml` describes only the legacy Streamlit prototype.
- `.github/workflows/celery-worker.yml` runs a worker + beat for a 420 s window on a schedule ("burst"): it can run due periodic tasks if a
  burst overlaps their time, it is **not** a supervised scheduler (a monthly 02:00 task is only run if a burst happens then).

## Rules a deployment must respect
1. **Exactly one beat process** for the whole system (two beats = every periodic task runs twice: invoices, reminders, purges). Workers may be many.
2. A worker is a **supervised** process (the host restarts it; `celery -A api.tasks.celery_app worker -l info --concurrency=N`). N is bounded by RAM:
   each process may load the embedding model (torch). With ≤ 1 GB use `--pool=solo` or `--concurrency=1`.
3. Broker and result backend: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (Redis; `rediss://` is handled). Without a broker, `apply_async` fails
   fast and the document stays `pending` (a recovery task exists).
4. Health: `celery -A api.tasks.celery_app inspect ping -t 5` (exit code 0 = a worker answered) and the queue depth (`LLEN celery` in Redis);
   alert if a task is older than its schedule. Task outcomes are exported as the Prometheus counter `celery_tasks_total`.
5. Idempotence is not uniform: 25 of 105 tasks contain an idempotence marker (heuristic scan). The billing tasks `generate_monthly_invoices`,
   `grant_monthly_plan_credits`, `auto_refill_credits` and `mark_overdue_invoices` are guarded (period key, row locks, conditional UPDATE);
   `send_invoice_reminders` has **no** guard (a second run re-sends). This is why rule 1 is strict. Candidate hardening: a Redis `SET NX` lock per periodic task.

## Options (costs are ESTIMATES: check the provider's current pricing page; no service was created)
| Option | API | Worker + beat | Pros | Limits |
|---|---|---|---|---|
| A. Current host, paid plan with a background worker | existing web service | 2 extra services from `deploy/render.worker.example.yaml` (worker, beat) | same provider, simple | recurring cost per service; free web services cannot run background workers |
| B. Low-cost VM (any small VPS with ≥ 2 GB RAM) | stays where it is | one VM running worker + beat under systemd or docker compose | cheapest per GB of RAM | you operate it (updates, monitoring, backups); needs the broker reachable (TLS Redis) |
| C. Keep the GitHub Actions "burst" | unchanged | scheduled workflow | no extra cost | not a scheduler: monthly/daily jobs can be missed, 420 s window, shared runners, secrets in CI; acceptable only as a stop-gap |

Recommendation (not a decision): B or A for production; C only until one of them exists. **Blocker**: the plan used today cannot run a persistent
worker if it is a free web service; the actual plan is not visible from the repository.

## Verification before calling it "in production"
`inspect ping` answers from the production broker, a due periodic task shows an execution in the logs at its time, the queue drains after an upload.
None of this has been observed.
