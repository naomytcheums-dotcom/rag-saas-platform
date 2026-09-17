#!/bin/sh
# Real "plan B" for running Celery without paying for a second Render
# service (Render's own Background Worker has no free tier -- $7/mo
# minimum, confirmed live on the dashboard). Runs the Celery worker as
# a background process inside the SAME free web service container,
# then execs gunicorn as PID 1 so Render's own process/port monitoring
# still targets the real web process.
#
# Real, honest risk, not hidden: this container's free tier has 512MB
# RAM total, and this app's heavy ML deps (torch, sentence-transformers,
# ultralytics, opencv) get imported by BOTH gunicorn (via api.main) AND
# the Celery worker (via celery_app.py's own `include=[...]` task
# module list) independently -- combined memory use may exceed what
# the free tier allows. If this container starts crash-looping (OOM)
# after this change, that's the honest answer: this specific free tier
# cannot run both in one container, and a paid worker (or a separate,
# more RAM-generous host) is genuinely required, not a config mistake
# to keep tuning around.
#
# --pool=solo: a single-threaded, single-process worker with no child
# processes of its own -- the lowest-memory Celery worker mode,
# appropriate for a resource-constrained free container, not a
# production-scale worker (real trade-off: only one task at a time).
celery -A api.tasks.celery_app worker --loglevel=info --pool=solo --concurrency=1 &

exec gunicorn -c gunicorn.conf.py api.main:app
