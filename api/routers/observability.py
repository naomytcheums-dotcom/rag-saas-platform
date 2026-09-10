"""
Partie 13.1/13.3 -- metrics summary + alerting/incidents. Global
(require_admin), same tier as admin_dashboard.py's monitoring/logs
endpoints -- these are platform-operational concerns, not org data.
GET /monitoring/{health,resources,queues} are NOT duplicated here --
they already exist for real in admin_dashboard.py (Partie 11.5).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_admin
from api.models.user import User
from api.schemas.observability import (
    AlertChannelCreateRequest, AlertChannelResponse, AlertChannelUpdateRequest, AlertHistoryResponse,
    AlertRuleCreateRequest, AlertRuleResponse, AlertRuleTestResponse, AlertRuleUpdateRequest,
    IncidentCreateRequest, IncidentResponse, IncidentUpdateRequest, MetricsSummaryResponse,
)
from api.security.tracing import tracing_status
from api.services import alerting, app_metrics

router = APIRouter(tags=["Observability"])


@router.get("/monitoring/metrics", response_model=MetricsSummaryResponse)
async def get_metrics_summary_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await app_metrics.get_metrics_summary(db)


@router.get("/monitoring/tracing/status")
async def get_tracing_status_endpoint(_admin: User = Depends(require_admin)):
    return tracing_status()


# -- 13.3 alert channels --------------------------------------------------

@router.get("/alerting/channels", response_model=list[AlertChannelResponse])
async def list_alert_channels_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await alerting.list_alert_channels(db, organization_id=None)


@router.post("/alerting/channels", response_model=AlertChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_channel_endpoint(body: AlertChannelCreateRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    channel = await alerting.create_alert_channel(db, organization_id=None, name=body.name, type_=body.type, config=body.config)
    await db.commit()
    return channel


@router.patch("/alerting/channels/{channel_id}", response_model=AlertChannelResponse)
async def update_alert_channel_endpoint(channel_id: uuid.UUID, body: AlertChannelUpdateRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        channel = await alerting.update_alert_channel(db, channel_id, **body.model_dump())
    except alerting.AlertChannelNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    await db.commit()
    return channel


@router.delete("/alerting/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_channel_endpoint(channel_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        await alerting.delete_alert_channel(db, channel_id)
    except alerting.AlertChannelNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    await db.commit()


# -- 13.3 alert rules -------------------------------------------------------

@router.get("/alerting/rules", response_model=list[AlertRuleResponse])
async def list_alert_rules_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await alerting.list_alert_rules(db, organization_id=None)


@router.post("/alerting/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule_endpoint(body: AlertRuleCreateRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rule = await alerting.create_alert_rule(db, organization_id=None, name=body.name, metric=body.metric, operator=body.operator, threshold=body.threshold, severity=body.severity, channel_id=body.channel_id, user_id=admin.id)
    await db.commit()
    return rule


@router.patch("/alerting/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule_endpoint(rule_id: uuid.UUID, body: AlertRuleUpdateRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        rule = await alerting.update_alert_rule(db, rule_id, **body.model_dump())
    except alerting.AlertRuleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    await db.commit()
    return rule


@router.delete("/alerting/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule_endpoint(rule_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        await alerting.delete_alert_rule(db, rule_id)
    except alerting.AlertRuleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    await db.commit()


@router.post("/alerting/rules/{rule_id}/test", response_model=AlertRuleTestResponse)
async def test_alert_rule_endpoint(rule_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        return await alerting.test_alert_rule(db, rule_id)
    except alerting.AlertRuleNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")


@router.get("/alerting/history", response_model=list[AlertHistoryResponse])
async def get_alert_history_endpoint(limit: int = 50, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await alerting.get_alert_history(db, organization_id=None, limit=limit)


# -- 13.3 incidents -----------------------------------------------------------

@router.get("/alerting/incidents", response_model=list[IncidentResponse])
async def list_incidents_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await alerting.list_incidents(db, organization_id=None)


@router.post("/alerting/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident_endpoint(body: IncidentCreateRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    incident = await alerting.create_incident(db, organization_id=None, title=body.title, description=body.description, severity=body.severity, user_id=admin.id)
    await db.commit()
    return incident


@router.patch("/alerting/incidents/{incident_id}", response_model=IncidentResponse)
async def update_incident_endpoint(incident_id: uuid.UUID, body: IncidentUpdateRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        incident = await alerting.update_incident(db, incident_id, **body.model_dump())
    except alerting.IncidentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    await db.commit()
    return incident


@router.post("/alerting/incidents/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident_endpoint(incident_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        incident = await alerting.resolve_incident(db, incident_id)
    except alerting.IncidentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    await db.commit()
    return incident
