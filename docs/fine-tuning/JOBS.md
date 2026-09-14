# Jobs

## Real submission (`submit_job`)

`POST /fine-tuning/jobs?org_id=...` (`{dataset_id, name, base_model?,
provider?, hyperparameters?}`) requires a real, `ready` dataset --
persists a real, `pending` `FineTuningJob` row, then dispatches a real
Celery task (`submit_fine_tuning_job`) rather than blocking the HTTP
request on a real, slow provider round-trip:

1. Downloads the dataset's own real, already-validated file.
2. Uploads it to the real provider (`POST /files`, `purpose=fine-tune`).
3. Creates the real remote fine-tuning job (`POST /fine_tuning/jobs`),
   persisting the provider's own real `id` as `provider_job_id` --
   required to ever poll status or cancel this job again later.

A real, honest `failed` status (with a real, readable `error_message`)
on a missing API key, a real network error, or a real provider 4xx/5xx
-- never a crash, never a fabricated "submitted."

## Real status polling (`check_job_status`)

Real provider fine-tuning jobs take minutes to hours; no real provider
exposes a webhook this codebase can rely on universally, so
`check_fine_tuning_status` (Celery, every 10 minutes) polls every
real, still-`running` job. On a real `succeeded` status, creates the
real `FineTunedModel` row (idempotent -- a real, second check on an
already-`succeeded` job never creates a duplicate). Any other real,
in-progress provider status (`validating_files`, `queued`, `running`,
...) leaves this codebase's own status as `running` -- an honest,
coarser real state, not a 1:1 mirror of every provider-specific
sub-phase.

## Cancellation

`POST /fine-tuning/jobs/{id}/cancel` -- real, only for a `pending`/
`running` job; calls the real provider's own cancel endpoint first
(when a real `provider_job_id` exists), then marks the row
`cancelled`.

## Endpoints

- `GET /fine-tuning/jobs?org_id=...` -- list.
- `GET /fine-tuning/jobs/{id}` -- one job.
- `GET /fine-tuning/jobs/{id}/metrics` -- real, provider-reported
  metrics (`trained_tokens`, etc.).
