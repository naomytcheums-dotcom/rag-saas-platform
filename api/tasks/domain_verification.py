"""
Partie 1.4.4 -- periodic custom-domain DNS-verification polling, run by
Celery Beat (api/tasks/celery_app.py's beat_schedule) every
DOMAIN_VERIFICATION_INTERVAL_SECONDS (default 5 minutes).

Same asyncio.run() bridge as api/tasks/ssl_certificate_renewal.py, and
for the identical reason: the real work (a real async DNS lookup per
domain, api/security/custom_domains.py's check_domain_dns_txt_record)
needs to stay async for the FastAPI routes that also call it, so
duplicating it as a parallel sync implementation just for these two
tasks would be needless, error-prone duplication.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.security.custom_domains import check_all_pending_domains, poll_domain_verification
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _check_pending_domain_verifications_async() -> dict[str, int]:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            results = await check_all_pending_domains(db)
            await db.commit()
            return results
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.domain_verification.check_pending_domain_verifications")
def check_pending_domain_verifications() -> dict[str, int]:
    """
    Item 2's literal periodic task -- polls every `pending` custom
    domain (api/security/custom_domains.py's check_all_pending_domains),
    activating those whose DNS now matches and marking `failed` those
    that have exhausted DOMAIN_VERIFICATION_MAX_ATTEMPTS or
    DOMAIN_VERIFICATION_TIMEOUT_MINUTES, leaving the rest untouched to
    be checked again next sweep. Idempotent and safe on any schedule --
    a domain that's already `active`/`failed` is never selected by
    check_all_pending_domains's own query. Returns
    `{"activated": N, "failed": N, "still_pending": N}`, mainly so a
    manual invocation or test can assert on it.
    """
    result = asyncio.run(_check_pending_domain_verifications_async())
    logger.info(
        "check_pending_domain_verifications: activated=%d failed=%d still_pending=%d",
        result["activated"], result["failed"], result["still_pending"],
    )
    return result


async def _poll_one_domain_async(domain: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            try:
                await poll_domain_verification(db, domain)
                await db.commit()
            except ValueError:
                # The domain was deleted between being scheduled and
                # this task actually running -- nothing left to do.
                pass
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.domain_verification.poll_one_domain")
def poll_one_domain(domain: str) -> None:
    """
    The one-off follow-up check
    api/security/custom_domains.py's schedule_domain_verification
    dispatches right after a domain is added -- a head start ahead of
    the next periodic sweep, not a replacement for it.
    """
    asyncio.run(_poll_one_domain_async(domain))
