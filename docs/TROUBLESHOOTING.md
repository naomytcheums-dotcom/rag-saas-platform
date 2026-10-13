# Troubleshooting guide

Every entry below was met while running the platform (see `docs/project-handover/15_END_TO_END_VALIDATION_REPORT.md`). Commands assume the repository virtualenv.

## Installation and start-up
| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: pgvector` (or any package) | wrong Python interpreter | use the project virtualenv: `.venv\Scripts\python.exe` (Windows) or `.venv/bin/python` |
| `Field required` for `JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `SUPPORT_EMAIL`, `AUDIT_LOG_HMAC_SECRET_KEY` | settings missing; JWT/session secrets also need at least 32 characters | copy `.env.example` and fill them, or export them |
| `Refusing to run: DATABASE_URL is a local database whose name does not look disposable` | the test guard protects real databases | tests and scripts must target a database whose name contains `test`, `pytest`, `scratch`, `disposable`, `throwaway` or `tmp` |
| `alembic upgrade head` fails on `CREATE EXTENSION vector` | PostgreSQL without pgvector | use the `pgvector/pgvector` image or install the extension |
| API starts but every call is 500 after a deploy | code deployed before the migrations (for example `users.job_title`) | `python scripts/migrate.py` (rehearsal) then `--apply`, then deploy |
| `EMAXCONNSESSION` from Supabase | too many connections on the session-mode pooler | use the transaction pooler (port 6543) and keep the small pool in `api/database.py` |

## Documents and search
| Symptom | Check | Fix |
|---|---|---|
| Document stays `pending` | is a Celery worker running on the same Redis? `requeue-stale-pending-documents` needs beat | start `celery -A api.tasks.celery_app worker` (Windows: `-P solo`, beat as a separate process) |
| Document `failed` | `GET /documents/{id}` -> `indexing_error` | corrupt file, OCR binaries missing (Tesseract/poppler), or the embedding model not downloadable offline (`HF_HUB_OFFLINE`) |
| Upload answers 503 naming `S3_DOCUMENTS_BUCKET_NAME` | object storage not configured | set the `S3_*` variables (MinIO locally: endpoint `http://localhost:9000`) |
| Upload answers 400 `file is empty` / `not a valid PDF...` | validation by real content | upload a real file; the limit is 50 MB |
| Search returns fewer than `top_k` results | the default `score_threshold` 0.5 is relative to the best result | pass `score_threshold: 0` or set it in the organization settings |
| After changing the embedding model old documents are no longer found | chunks embedded by another model are ignored at query time | re-index (`POST /organizations/{id}/documents/reindex` or per document) |
| `dimension_mismatch_excluded` in logs | chunks of another vector size | re-index with the current model |

## Chat and LLM
| Symptom | Fix |
|---|---|
| `No API key configured for provider 'anthropic'` | set the organization provider (`PATCH /organizations/{id}/settings` with `llm_provider` / `llm_model`) or the agent's `model_config`; precedence: caller > agent > organization > global default |
| Ollama: connection refused | start the server (`ollama serve` or the container) and set `OLLAMA_BASE_URL`; check `ollama list` for the model name |
| Ollama answers very slowly the first time | the model is loaded into memory on the first call (minutes for a 7B model on CPU); keep it warm and raise `LLM_TIMEOUT` / `PROMPT_INJECTION_CONFIRM_TIMEOUT_SECONDS` |
| Chat answers "I could not find it in the documents" | nothing relevant was retrieved: check `POST /organizations/{id}/search`, then `GET /responses/{id}/trace` |
| Chat stream ends with `Guardrail violation: prompt_injection...` | the agent's injection detector blocked the question before generation; legitimate text can be flagged (measured false-positive rate 2 to 12 % depending on the second opinion) |

## Frontend
| Symptom | Fix |
|---|---|
| `tsc` says `Cannot find name 'LayoutProps'` | run `npx next typegen` first |
| `Symlink [project]/node_modules is invalid` with Turbopack (a second git worktree) | start with `next dev --webpack`, or install `node_modules` in that worktree |
| Chat page shows "Regenerating..." forever in development | Fast Refresh rebuilt during a stream; reload the page |
| CORS error from the browser | the page origin must equal `FRONTEND_URL` (or a Vercel preview URL of this project) |

## Tests
| Symptom | Fix |
|---|---|
| Connection refused on `localhost:9000` | MinIO is not running (S3 tests); in CI this was memory pressure |
| `SECRET_ENCRYPTION_KEY must be set` | export a Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| PostgreSQL-only tests are skipped | set `TEST_DATABASE_URL`, `P0_PG_TEST_URL` (a `pytest_*` database), `RAG_DISPOSABLE_PG_URL` + `RAG_DISPOSABLE_PG_CONFIRM`, and `PGVECTOR_REAL_TEST=1` |
| Never run pytest with the production `.env` | use `bash scripts/run_tests_local.sh ...` |
