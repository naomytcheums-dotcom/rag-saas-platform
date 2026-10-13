#!/bin/bash
# Starts the isolated E2E API (port 8010) and a Celery worker. Logs: api.log, worker.log in this folder.
cd "$(dirname "$0")/../.."
export PATH="/c/Users/NITROV15/Downloads/rag-saas-platform/.venv/Scripts:$PATH"
source scripts/test_env/e2e_stack_env.sh
L="${E2E_LOG_DIR:-.}"
nohup python -m uvicorn api.main:app --host 127.0.0.1 --port 8010 > $L/api.log 2>&1 &
nohup python -m celery -A api.tasks.celery_app worker -P solo -l info > $L/worker.log 2>&1 &
