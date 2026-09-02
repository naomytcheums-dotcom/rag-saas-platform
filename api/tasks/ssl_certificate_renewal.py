"""
Partie 1.4.3 -- periodic SSL certificate renewal/expiry checks, run by
Celery Beat (api/tasks/celery_app.py's beat_schedule).

Unlike every other task in this package (account_purge.py,
jwt_key_rotation.py, token_blacklist_cleanup.py), this one bridges into
ASYNC code via asyncio.run() rather than using a plain sync SQLAlchemy
engine -- a deliberate departure. Those tasks are simple enough that a
sync-engine duplicate of their (tiny) query logic costs nothing; the
certificate logic in api/security/ssl_certificates.py is substantial,
real ACME-protocol code that needs to stay async anyway (for the
FastAPI routes that also call it, so a real, possibly multi-second
Let's Encrypt round trip never blocks the event loop) -- maintaining a
second, parallel sync implementation of that logic just for this task
would be significant, error-prone duplication of cryptographic
protocol code for no real benefit. asyncio.run() from a plain
synchronous Celery task body is the standard, correct way to bridge
into it: Celery's worker call stack has no already-running event loop
to conflict with.

**Real-world limitation this task cannot paper over** (see
api/security/ssl_certificates.py's renew_ssl_certificate docstring):
DNS-01 renewal needs a NEW DNS TXT record published by the Owner every
time, since challenges are single-use. This task starts that process
(opens a fresh order) -- it cannot complete it unattended, because
nothing in this deployment can publish DNS records on the Owner's
behalf. A renewed-to-`pending_dns01` certificate genuinely needs a
human to finish the job, exactly like a first-time issuance.
"""

import asyncio
import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.ssl_certificate import SSLCertificate, SSLCertificateStatus
from api.security.ssl_certificates import renew_ssl_certificate
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _check_ssl_renewals_async() -> int:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    renewed_count = 0
    try:
        async with session_factory() as db:
            cutoff = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=settings.SSL_RENEWAL_WINDOW_DAYS)
            due = (await db.scalars(
                select(SSLCertificate).where(
                    SSLCertificate.status == SSLCertificateStatus.issued.value,
                    SSLCertificate.expires_at <= cutoff,
                )
            )).all()
            for certificate in due:
                try:
                    await renew_ssl_certificate(db, certificate.domain)
                    await db.commit()
                    renewed_count += 1
                    logger.info(
                        "check_ssl_renewals: started a renewal order for '%s' -- awaiting the Owner's new DNS-01 TXT record",
                        certificate.domain,
                    )
                except (ValueError, EnvironmentError, RuntimeError) as exc:
                    await db.rollback()
                    logger.warning("check_ssl_renewals: could not start a renewal for '%s': %s", certificate.domain, exc)
    finally:
        await engine.dispose()
    return renewed_count


@celery_app.task(name="api.tasks.ssl_certificate_renewal.check_ssl_renewals")
def check_ssl_renewals() -> int:
    """
    Item 5's literal "tâche périodique de renouvellement" -- finds
    every `issued` certificate expiring within SSL_RENEWAL_WINDOW_DAYS
    (default 30) and starts a real renewal order for each. Idempotent
    and safe on any schedule: a certificate already mid-renewal
    (status=pending_dns01) is simply not selected by this query again
    until it either completes or someone calls DELETE to abandon it.
    Returns how many renewal orders were started, mainly so a manual
    invocation or test can assert on it.
    """
    return asyncio.run(_check_ssl_renewals_async())


async def _check_ssl_expirations_async() -> list[str]:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with session_factory() as db:
            now = dt.datetime.now(dt.timezone.utc)
            expired = (await db.scalars(
                select(SSLCertificate.domain).where(
                    SSLCertificate.status == SSLCertificateStatus.issued.value,
                    SSLCertificate.expires_at < now,
                )
            )).all()
            return list(expired)
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.ssl_certificate_renewal.check_ssl_expirations")
def check_ssl_expirations() -> list[str]:
    """
    Item 5's literal "tâche de vérification des certificats expirés" --
    a safety net alongside check_ssl_renewals above, not a replacement
    for it: this only LOGS any `issued` certificate whose expires_at
    has already passed (renewal should have caught it
    SSL_RENEWAL_WINDOW_DAYS earlier -- reaching this state means a
    renewal silently failed, or the Owner never completed the DNS-01
    step for one). Returns the list of expired domains, mainly so a
    manual invocation or test can assert on it.
    """
    expired_domains = asyncio.run(_check_ssl_expirations_async())
    for domain in expired_domains:
        logger.warning(
            "check_ssl_expirations: '%s' has an EXPIRED certificate still marked issued -- renewal did not complete in time",
            domain,
        )
    return expired_domains
