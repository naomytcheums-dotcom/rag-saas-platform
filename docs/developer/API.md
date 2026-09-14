# API

The full REST API reference (auth, errors, rate limits, pagination, and
per-resource endpoints) lives under [`docs/api/`](../api/) — start at
[`docs/api/OVERVIEW.md`](../api/OVERVIEW.md). This page covers how the
API is organized in code, for contributors.

## Organization

89 routers under `api/routers/`, one per feature area, each paired
with:

- `api/schemas/<feature>.py` — Pydantic request/response models.
- `api/security/<feature>.py` — access control checks.
- `api/services/<feature>.py` — business logic (usually).
- `api/tasks/<feature>.py` — Celery tasks, when the feature has
  background work.

## Path conventions

Most features nest under an organization:
`/organizations/{org_id}/<feature>/...`. A few — notably fine-tuning —
use flat paths with `org_id` as a required query parameter instead
(`/fine-tuning/...?org_id=...`), because that's what Partie 24's own
spec called for; FastAPI resolves a query parameter named `org_id` the
same way it resolves a path parameter of the same name, so the
dependency-injection pattern doesn't change.

## Public API

A separate, more stable public surface is exposed under
`api/routers/public_api.py` and versioned via
`api/routers/api_versioning.py`, intended for external integrations
rather than the dashboard's own internal calls.

## OpenAPI

The live OpenAPI schema is generated from the actual FastAPI app
(`app.openapi()`), not hand-maintained — see
[`docs/api/openapi.json`](../api/openapi.json),
[Swagger UI](../api/swagger.md), and [Redoc](../api/redoc.md).
