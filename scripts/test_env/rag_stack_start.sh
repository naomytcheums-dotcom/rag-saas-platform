#!/bin/bash
# Private RAG-value-chain stack: API on 8030 + own Celery worker (Redis DB 14, database rag_test_rag, Ollama qwen2.5:3b).
cd "$(dirname "$0")/../.."
export PATH="/c/Users/NITROV15/Downloads/rag-saas-platform/.venv/Scripts:$PATH"
source scripts/test_env/rag_stack_env.sh
L="${RAG_LOG_DIR:-.}"
nohup python -m uvicorn api.main:app --host 127.0.0.1 --port 8030 > $L/rag_api.log 2>&1 &
echo $! > $L/rag_api.pid
nohup python -m celery -A api.tasks.celery_app worker -P solo -l info -n rag14@%h > $L/rag_worker.log 2>&1 &
echo $! > $L/rag_worker.pid
