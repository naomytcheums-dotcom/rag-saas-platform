# Models

## Real, automatic creation

A `FineTunedModel` row is created automatically the moment
`check_job_status` sees a real `succeeded` job -- never manually.
`provider_model_id` is the real, provider-issued string a real
`chat_completion` call's own `model=` kwarg needs (e.g. OpenAI's
`ft:gpt-4o-mini-2024-07-18:acme::abc123`), distinct from `base_model`
(what it was trained FROM).

## Status vs. deployed -- two real, different questions

`status` (`available`/`deprecated`) is this model's own real
LIFECYCLE. `deployed` (a real, separate boolean) is whether an
organization has actually opted to make it selectable for real use
right now. A real, available, never-deployed model is a normal,
honest state; a deprecated, still-deployed one is a real, actionable
warning, not a contradiction this schema makes impossible to
represent.

`POST /fine-tuning/models/{id}/deploy` refuses a real `deprecated`
model outright (400) -- `POST .../undeploy` always succeeds.

## Endpoints

- `GET /fine-tuning/models?org_id=...` -- list.
- `GET /fine-tuning/models/{id}` -- one model.
- `DELETE /fine-tuning/models/{id}`.
- `POST /fine-tuning/models/{id}/deploy` / `.../undeploy`.
