# Testing

## Backend

pytest, under `tests/backend/<feature>/` for feature-specific suites
(e.g. `tests/backend/autonomous/`, `tests/backend/fine-tuning/`) and
`tests/test_*.py` at the repo root for cross-cutting/older suites.

```bash
cd api
pytest ../tests -q
```

Before adding a new test file under `tests/backend/<feature>/`, check
`tests/test_*.py` for a basename collision — several feature areas
needed a more specific name than the obvious one (e.g.
`test_autonomous_agents.py` instead of colliding with the pre-existing
`tests/test_agents.py`).

## Frontend

Vitest.

```bash
cd frontend
npm test
```

## Documentation tests

`tests/docs/` validates the documentation itself, not just the code:

- `test_links.py` — every relative link in `docs/` and the root `*.md`
  files resolves to a real file.
- `test_examples.py` — code examples in the docs (SDK snippets, curl
  commands) are syntactically valid and, where feasible, exercised
  against the real client libraries.
- `test_api_reference.py` — every endpoint documented in
  [`docs/api/`](../api/) exists in the real FastAPI app, and the live
  OpenAPI export is up to date.

```bash
pytest tests/docs -q
```

## What isn't tested against a live environment

Some real-provider integrations (Google Calendar/Sheets, live Docker
builds, live Anthropic fine-tuning credit-gated calls) are tested
against mocked/stubbed boundaries rather than the real external service
in this environment — this is documented per-feature rather than left
implicit; see e.g. [`src/README.md`](../../src/README.md#current-limitations).
