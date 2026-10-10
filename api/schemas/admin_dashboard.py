"""Request/response bodies for Partie 11 (admin dashboard/orgs/users/subscriptions/monitoring/logs)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from api.models.admin import SubscriptionStatus


# -- 11.1 stats -----------------------------------------------------------

class GlobalStatsResponse(BaseModel):
    users: dict
    organizations: dict
    documents: dict
    agents: dict
    conversations: dict
    api_usage: dict
    revenue: dict
    generated_at: dt.datetime


# -- 11.2 organizations -----------------------------------------------------

class OrganizationAdminResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_suspended: bool
    suspended_reason: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class OrganizationAdminListResponse(BaseModel):
    items: list[OrganizationAdminResponse]
    total: int
    limit: int
    offset: int


class OrganizationUpdateAdminRequest(BaseModel):
    name: str | None = None


class OrganizationSuspendRequest(BaseModel):
    reason: str | None = None


class OrganizationMemberAdminResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    joined_at: dt.datetime


# -- 11.3 users ---------------------------------------------------------------

class UserAdminResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    is_active: bool
    is_email_verified: bool
    role: str
    suspended_reason: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class UserAdminListResponse(BaseModel):
    items: list[UserAdminResponse]
    total: int
    limit: int
    offset: int


class UserUpdateAdminRequest(BaseModel):
    full_name: str | None = None
    company: str | None = None


class UserSuspendRequest(BaseModel):
    reason: str | None = None


class UserSessionAdminResponse(BaseModel):
    id: uuid.UUID
    device_info: str | None
    ip_address: str | None
    created_at: dt.datetime
    last_seen_at: dt.datetime

    model_config = {"from_attributes": True}


# -- 11.4 subscriptions ---------------------------------------------------------

class PlanResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    monthly_price_cents: int
    max_documents: int | None
    max_agents: int | None
    max_members: int | None
    is_active: bool
    # Phase 5, Étape 2 correctif (Étape 3 audit) -- these two fields were
    # added to Plan/api.schemas.billing.PlanResponse in Étape 2, but this
    # is the schema the REAL admin CRUD endpoint (POST/PATCH /admin/plans,
    # api/routers/admin_subscriptions.py) actually uses -- without them
    # here, an admin had no real way to set a Plan's Paystack plan code
    # through the API at all. api.schemas.billing.PlanCreateRequest/
    # PlanUpdateRequest are never imported by any router (confirmed by
    # audit) -- this is the one that matters.
    paystack_plan_code_monthly: str | None = None
    paystack_plan_code_yearly: str | None = None

    model_config = {"from_attributes": True}


class PlanCreateRequest(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    monthly_price_cents: int = Field(default=0, ge=0, le=100_000_000)
    max_documents: int | None = Field(default=None, ge=0, le=1_000_000_000)
    max_agents: int | None = Field(default=None, ge=0, le=1_000_000_000)
    max_members: int | None = Field(default=None, ge=0, le=1_000_000_000)
    paystack_plan_code_monthly: str | None = Field(default=None, max_length=100)
    paystack_plan_code_yearly: str | None = Field(default=None, max_length=100)


class PlanUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    monthly_price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    max_documents: int | None = Field(default=None, ge=0, le=1_000_000_000)
    max_agents: int | None = Field(default=None, ge=0, le=1_000_000_000)
    max_members: int | None = Field(default=None, ge=0, le=1_000_000_000)
    is_active: bool | None = None
    paystack_plan_code_monthly: str | None = Field(default=None, max_length=100)
    paystack_plan_code_yearly: str | None = Field(default=None, max_length=100)


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    plan_id: uuid.UUID
    status: SubscriptionStatus
    current_period_end: dt.datetime | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class SubscriptionUpdateRequest(BaseModel):
    plan_id: uuid.UUID | None = None
    status: SubscriptionStatus | None = None


class SubscriptionCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class SubscriptionExtendRequest(BaseModel):
    days: int = Field(ge=1, le=3650)


class RevenueStatsResponse(BaseModel):
    mrr_cents: int
    arr_cents: int
    active_subscriptions: int
    arpu_cents: int
    churn_last_30d: int


# -- 11.5 monitoring ------------------------------------------------------------

class SystemHealthResponse(BaseModel):
    database: str
    redis: str
    celery: str
    checked_at: dt.datetime


class ResourceUsageResponse(BaseModel):
    cpu_percent: float
    cpu_count: int
    memory_used_bytes: int
    memory_total_bytes: int
    memory_percent: float
    disk_used_bytes: int
    disk_total_bytes: int
    disk_percent: float


class QueueStatusResponse(BaseModel):
    active_tasks: int
    scheduled_tasks: int
    reserved_tasks: int
    workers_online: int


# -- 11.6 logs --------------------------------------------------------------

class SystemLogResponse(BaseModel):
    id: uuid.UUID
    level: str
    logger_name: str
    message: str
    module: str | None
    function: str | None
    line: int | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class SystemLogListResponse(BaseModel):
    items: list[SystemLogResponse]
    total: int
    limit: int
    offset: int


class LogsStatsResponse(BaseModel):
    by_level: dict[str, int]
    top_loggers: dict[str, int]
