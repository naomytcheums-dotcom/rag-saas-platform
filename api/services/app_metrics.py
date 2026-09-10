"""
Partie 13.1 -- GET /monitoring/metrics's own summary (distinct from GET
/metrics's raw Prometheus text exposition, api/monitoring.py). Business
gauges (organizations/users/conversations counts) are deliberately NOT
added as prometheus_client Gauges: in PROMETHEUS_MULTIPROC_DIR mode,
this project's real Gunicorn/multi-worker deployment, a Gauge computed
fresh per-scrape from the DB has no correct multiprocess aggregation
mode (sum/max/min/livesum all give a wrong number for "how many
organizations exist" reported by N worker processes) -- returning them
here, computed once per real API call, sidesteps that correctness trap
entirely rather than shipping a metric that's quietly wrong under load.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.admin import Subscription, SubscriptionStatus
from api.models.conversation import Conversation
from api.models.organization import Organization
from api.models.user import User
from api.monitoring import CELERY_TASKS_TOTAL, HTTP_REQUESTS_TOTAL, REQUEST_DURATION_SECONDS


async def get_metrics_summary(db: AsyncSession) -> dict:
    organizations = await db.scalar(select(func.count()).select_from(Organization)) or 0
    users = await db.scalar(select(func.count()).select_from(User)) or 0
    conversations = await db.scalar(select(func.count()).select_from(Conversation)) or 0
    active_subscriptions = await db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.active)) or 0

    return {
        "business": {
            "organizations": organizations,
            "users": users,
            "conversations": conversations,
            "active_subscriptions": active_subscriptions,
        },
        # Real counter/histogram sample counts read straight from this
        # process's own in-memory registry -- the same data GET /metrics
        # exposes in Prometheus text format, summarized here for a
        # human-readable admin view. In multiprocess mode this reflects
        # only the worker that happened to handle THIS request, not the
        # fleet-wide total (honest limitation, same reasoning as this
        # module's own docstring) -- GET /metrics itself is the correct,
        # complete source in that deployment shape.
        "http_requests_total_samples": _sum_counter(HTTP_REQUESTS_TOTAL),
        "celery_tasks_total_samples": _sum_counter(CELERY_TASKS_TOTAL),
        "request_duration_observation_count": _sum_histogram_count(REQUEST_DURATION_SECONDS),
    }


def _sum_counter(counter) -> int:
    total = 0
    for metric in counter.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total"):
                total += sample.value
    return int(total)


def _sum_histogram_count(histogram) -> int:
    total = 0
    for metric in histogram.collect():
        for sample in metric.samples:
            if sample.name.endswith("_count"):
                total += sample.value
    return int(total)
