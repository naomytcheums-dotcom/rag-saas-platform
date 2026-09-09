"""Request/response bodies for Partie 9.1's own public `/v1/*` API."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


# --------------------------------------------------------------------- 9.1.1 Chat


class ChatRequest(BaseModel):
    message: str
    agent_id: str
    conversation_id: uuid.UUID | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    response: str
    citations: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------- 9.1.2 Documents


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    name: str
    metadata: dict = Field(default_factory=dict)


# ----------------------------------------------------------- 9.1.3 Knowledge bases


class KnowledgeBaseCreateRequest(BaseModel):
    name: str
    description: str | None = None
    config: dict | None = None


class KnowledgeBaseCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: dt.datetime


# ------------------------------------------------------------- 9.1.4 Conversations


class ConversationItem(BaseModel):
    id: uuid.UUID
    title: str
    created_at: dt.datetime
    updated_at: dt.datetime
    last_message_preview: str | None


class ConversationListResponse(BaseModel):
    items: list[ConversationItem]
    total: int
    limit: int
    offset: int


# -------------------------------------------------------------------- 9.1.5 Search


class PublicSearchRequest(BaseModel):
    query: str
    workspace_id: uuid.UUID | None = None
    filters: dict | None = None
    top_k: int = 5


class PublicSearchResponse(BaseModel):
    results: list[dict]
    total: int
    query: str
    metadata: dict = Field(default_factory=dict)


# --------------------------------------------------------------- 9.1.6 Agents/run


class AgentRunRequest(BaseModel):
    agent_id: str
    input: str
    conversation_id: uuid.UUID | None = None
    stream: bool = False


class AgentRunResponse(BaseModel):
    run_id: uuid.UUID
    output: str | None
    conversation_id: uuid.UUID | None
    metadata: dict = Field(default_factory=dict)


# ------------------------------------------------------------------- 9.1.7 Usage


class UsageMetric(BaseModel):
    name: str
    value: int
    unit: str
    timestamp: dt.datetime


class UsageResponse(BaseModel):
    period: str
    metrics: list[UsageMetric]
    # Real shape from api.security.usage.get_usage_summary: a list of
    # {"date", "metrics"} entries, one per day -- not a dict keyed by
    # date (dates aren't valid JSON object keys anyway).
    breakdown: list[dict]
    total: int


# --------------------------------------------------------------- 9.1.8 Analytics


class AnalyticsMetric(BaseModel):
    name: str
    value: float
    change_percentage: float | None
    trend: str


class AnalyticsResponse(BaseModel):
    period: str
    metrics: list[AnalyticsMetric]
    data: list[dict]
    summary: str


# ----------------------------------------------------------------------- 9.1.9 Embed


class EmbedRequest(BaseModel):
    text: str
    model: str | None = None


class EmbedResponse(BaseModel):
    embedding: list[float]
    model: str
    dimensions: int


# --------------------------------------------------------- Organization API key management


class OrganizationAPIKeyCreateRequest(BaseModel):
    name: str
    scopes: list[str]
    expires_at: dt.datetime | None = None


class OrganizationAPIKeyCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    key: str
    key_prefix: str
    scopes: list[str]
    expires_at: dt.datetime | None
    created_at: dt.datetime


class OrganizationAPIKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: dt.datetime | None
    last_used_at: dt.datetime | None
    created_at: dt.datetime
    revoked_at: dt.datetime | None

    model_config = {"from_attributes": True}
