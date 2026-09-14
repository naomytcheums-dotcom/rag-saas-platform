# Contributing

## Before you start

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for the system overview, and
the feature's own doc under [`docs/`](docs/) if you're changing an
existing subsystem. Check
[`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md) for the
history and rationale behind the area you're touching — many design
decisions (e.g. why autonomous agents are a separate table from agents,
why fine-tuning targets OpenAI/Mistral and not Anthropic) are
deliberate and documented there, not oversights.

## Project conventions

- **One module per feature area**, mirrored across `api/routers/`,
  `api/schemas/`, `api/security/`, `api/services/`, and (when there's
  background work) `api/tasks/`. Follow the existing pattern for the
  closest feature rather than inventing a new structure.
- **All LLM calls go through litellm**, not a provider SDK directly,
  unless the provider genuinely isn't covered by litellm for what you
  need (the fine-tuning REST clients in
  `api/services/fine_tuning_providers.py` are the one documented
  exception — see [`ARCHITECTURE.md`](ARCHITECTURE.md#llm-access-litellm)).
- **Every tenant-scoped table carries `org_id`** and should enable row
  -level security unless there's a specific reason not to.
- **`httpx`** is the standard client for third-party REST APIs
  (Twilio, Airbyte, Slack, OpenAI/Mistral fine-tuning, etc.) — don't add
  a new SDK dependency for a REST integration `httpx` can already do.
- **Test basename collisions**: before adding a new
  `tests/backend/<feature>/test_*.py` file, check `tests/test_*.py` at
  the repo root for an existing file with the same basename (several
  feature areas needed a more specific name, e.g.
  `test_autonomous_agents.py` instead of colliding with the existing
  `tests/test_agents.py`).
- **Field naming**: match this codebase's own conventions over a
  spec's literal wording when they conflict — e.g. object storage keys
  are always named `file_key` (`Document.file_key`, `MediaAsset.file_key`,
  `FineTuningDataset.file_key`), not `file_path`.

## Frontend conventions

- Light theme only. No dark mode.
- Orange-and-white gradient, consistent with the rest of the dashboard.
- No decorative progress bars or unnecessary loading chrome.
- No emojis in the UI.
- One `frontend/lib/services/<feature>.ts` client + matching
  `frontend/lib/hooks/*.ts` per API router, mirroring the backend
  feature split.

## Tests

- Backend: pytest, under `tests/backend/<feature>/` for feature-specific
  suites, `tests/test_*.py` for root-level/cross-cutting ones.
- Frontend: Vitest.
- Documentation: `tests/docs/` — real link, example, and API-reference
  validation, not just prose. See [`docs/developer/TESTING.md`](docs/developer/TESTING.md).
- Run the relevant suite locally before opening a PR. CI runs the full
  suite on every push.

## Commit and PR conventions

- Never commit `.env` or any file containing real secrets. A safety
  scan (`git diff --cached | grep` for known secret substrings) should
  come up empty before committing.
- Stage exact file lists, not `git add -A`.
- Keep PRs scoped to one feature area or one fix; don't bundle unrelated
  changes.

## Reporting a security issue

Do not open a public issue for a security vulnerability — see
[`SECURITY.md`](SECURITY.md).
