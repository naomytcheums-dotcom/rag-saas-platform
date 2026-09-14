# Stack

| Layer | Choice |
|---|---|
| API | FastAPI (async) |
| ORM / migrations | SQLAlchemy 2.0 async + Alembic |
| Database | PostgreSQL (Supabase) |
| Background jobs | Celery + Redis |
| LLM access | [litellm](https://github.com/BerriAI/litellm) (Anthropic, OpenAI, Mistral, others) |
| Object storage | S3-compatible |
| Frontend | Next.js, React, TypeScript |
| Frontend tests | Vitest |
| Backend tests | pytest |
| Vision / media | YOLOv8 (`ultralytics`, local inference), CLIP (`openai/clip-vit-base-patch32`) + faiss-cpu |
| Third-party REST clients | `httpx` (Twilio, Airbyte, Slack, OpenAI/Mistral fine-tuning, etc.) |

## Why these choices

- **litellm over provider SDKs directly** — one abstraction across
  providers means organization-level and per-agent model choice doesn't
  require provider-specific call sites throughout the codebase.
- **httpx as the universal REST client** — rather than adding a new SDK
  dependency per third-party integration, `httpx` is reused consistently
  (see [`ARCHITECTURE.md`](../../ARCHITECTURE.md#llm-access-litellm)).
- **Celery + Redis for background work** — document ingestion,
  evaluation runs, fine-tuning polling, and media processing are never
  inline in a request.

See the root [`ARCHITECTURE.md`](../../ARCHITECTURE.md) for how these
fit together.
