"""
Hardening Mission (§13) -- organization-scoped RAG-quality alerting ("Guardian").

Why this router exists: every route under `/alerting/*` (api/routers/observability.py)
is PLATFORM-admin-only and creates rules with `organization_id=None`. The RAG-quality
metrics (`recall_at_5`, `mrr`, `ndcg_at_5`, `hallucination_rate`, ...) are measured
PER ORGANIZATION from its own latest completed evaluation job, so a platform-level
rule can never read them -- no customer could configure Guardian at all. These
routes let an organization manage its OWN rules / channels / history:

- only RAG-quality metrics are accepted (infrastructure metrics such as `cpu_percent`
  are platform-wide and are not for tenants to read or alert on);
- every rule / channel is scoped to `org_id` -- another organization's id is a 404;
- permission `evaluation:manage` (Owner/Admin always pass).
"""

import re
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.alerting import AlertChannel, AlertChannelType, AlertOperator, AlertRule, AlertSeverity
from api.models.organization import OrganizationMember
from api.schemas.observability import AlertChannelResponse, AlertHistoryResponse, AlertRuleResponse, AlertRuleTestResponse
from api.security.permissions import require_permission
from api.services import alerting
from api.utils import MAX_PAGE_SIZE

router = APIRouter(tags=["quality-alerts"])

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


class QualityRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    metric: str
    operator: AlertOperator
    # Every RAG-quality metric is a rate/score in [0, 1].
    threshold: float = Field(ge=0.0, le=1.0)
    severity: AlertSeverity = AlertSeverity.medium
    channel_id: uuid.UUID | None = None

    @field_validator("metric")
    @classmethod
    def _real_rag_metric(cls, value: str) -> str:
        if value not in alerting.RAG_QUALITY_METRICS:
            raise ValueError(f"metric must be one of {sorted(alerting.RAG_QUALITY_METRICS)}")
        return value


class QualityRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    operator: AlertOperator | None = None
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    severity: AlertSeverity | None = None
    channel_id: uuid.UUID | None = None
    enabled: bool | None = None


class QualityChannelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: AlertChannelType
    config: dict

    @field_validator("config")
    @classmethod
    def _config_matches_type(cls, value: dict, info) -> dict:
        kind = info.data.get("type")
        if kind == AlertChannelType.email:
            email = value.get("email")
            if not isinstance(email, str) or not _EMAIL.match(email):
                raise ValueError('an email channel needs config {"email": "<address>"}')
            return {"email": email}
        if kind == AlertChannelType.webhook:
            url = value.get("webhook_url")
            parsed = urlparse(url) if isinstance(url, str) else None
            if parsed is None or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('a webhook channel needs config {"webhook_url": "https://..."} (https only, no credentials in the URL)')
            return {"webhook_url": url}
        raise ValueError("unsupported channel type")


async def _owned_rule(db: AsyncSession, org_id: uuid.UUID, rule_id: uuid.UUID) -> AlertRule:
    rule = await db.get(AlertRule, rule_id)
    if rule is None or rule.organization_id != org_id:
        raise _NOT_FOUND
    return rule


async def _require_own_channel(db: AsyncSession, org_id: uuid.UUID, channel_id: uuid.UUID | None) -> None:
    """A rule may only notify a channel of ITS OWN organization -- never a
    platform channel or another tenant's (that would send this organization's
    quality data to somebody else's inbox/webhook)."""
    if channel_id is None:
        return
    channel = await db.get(AlertChannel, channel_id)
    if channel is None or channel.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")


@router.get("/organizations/{org_id}/quality-alerts/metrics")
async def list_quality_metrics_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("evaluation:manage"))):
    return {"metrics": sorted(alerting.RAG_QUALITY_METRICS)}


@router.get("/organizations/{org_id}/quality-alerts/rules", response_model=list[AlertRuleResponse])
async def list_quality_rules_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db)):
    return await alerting.list_alert_rules(db, organization_id=org_id)


@router.post("/organizations/{org_id}/quality-alerts/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_quality_rule_endpoint(
    org_id: uuid.UUID, body: QualityRuleCreateRequest,
    caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    await _require_own_channel(db, org_id, body.channel_id)
    rule = await alerting.create_alert_rule(
        db, organization_id=org_id, name=body.name, metric=body.metric, operator=body.operator, threshold=body.threshold,
        severity=body.severity, channel_id=body.channel_id, user_id=caller.user_id,
    )
    await db.commit()
    return rule


@router.patch("/organizations/{org_id}/quality-alerts/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_quality_rule_endpoint(
    org_id: uuid.UUID, rule_id: uuid.UUID, body: QualityRuleUpdateRequest,
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    await _owned_rule(db, org_id, rule_id)
    await _require_own_channel(db, org_id, body.channel_id)
    rule = await alerting.update_alert_rule(db, rule_id, **body.model_dump())
    await db.commit()
    return rule


@router.delete("/organizations/{org_id}/quality-alerts/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quality_rule_endpoint(
    org_id: uuid.UUID, rule_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    await _owned_rule(db, org_id, rule_id)
    await alerting.delete_alert_rule(db, rule_id)
    await db.commit()


@router.post("/organizations/{org_id}/quality-alerts/rules/{rule_id}/test", response_model=AlertRuleTestResponse)
async def test_quality_rule_endpoint(
    org_id: uuid.UUID, rule_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    await _owned_rule(db, org_id, rule_id)
    return await alerting.test_alert_rule(db, rule_id)


@router.get("/organizations/{org_id}/quality-alerts/history", response_model=list[AlertHistoryResponse])
async def quality_alert_history_endpoint(
    org_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    return await alerting.get_alert_history(db, organization_id=org_id, limit=limit)


@router.get("/organizations/{org_id}/quality-alerts/channels", response_model=list[AlertChannelResponse])
async def list_quality_channels_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db)):
    return await alerting.list_alert_channels(db, organization_id=org_id)


@router.post("/organizations/{org_id}/quality-alerts/channels", response_model=AlertChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_quality_channel_endpoint(
    org_id: uuid.UUID, body: QualityChannelCreateRequest,
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    channel = await alerting.create_alert_channel(db, organization_id=org_id, name=body.name, type_=body.type, config=body.config)
    await db.commit()
    return channel


@router.delete("/organizations/{org_id}/quality-alerts/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quality_channel_endpoint(
    org_id: uuid.UUID, channel_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    channel = await db.get(AlertChannel, channel_id)
    if channel is None or channel.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    await alerting.delete_alert_channel(db, channel_id)
    await db.commit()
