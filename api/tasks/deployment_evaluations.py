"""Partie 7.3.8 -- the real Celery entry point for
`api/services/deployment_evaluations.py`'s own `run_deployment_evaluation`."""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.services.deployment_evaluations import run_deployment_evaluation
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


async def _run_deployment_evaluation_async(evaluation_id: str) -> str:
    engine = make_async_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            evaluation = await run_deployment_evaluation(db, uuid.UUID(evaluation_id))
            return evaluation.status if evaluation is not None else "not_found"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.deployment_evaluations.run_deployment_evaluation_task")
def run_deployment_evaluation_task(evaluation_id: str) -> str:
    """Item 4's own literal task -- exécute l'évaluation pré-déploiement en arrière-plan."""
    return asyncio.run(_run_deployment_evaluation_async(evaluation_id))
