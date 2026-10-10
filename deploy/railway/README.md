# Railway

Create three services from this repository, each with `railway.json` as the config and the same variables (`DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, ...):

1. **api** - default start command (gunicorn).
2. **worker** - start command override: `celery -A api.tasks.celery_app worker --loglevel=info`
3. **beat** - start command override: `celery -A api.tasks.celery_app beat --loglevel=info` (exactly one replica)

Add the Railway Redis plugin for `REDIS_URL`. Use an external PostgreSQL with pgvector (for example Supabase). Not deployed by the authoring session.
