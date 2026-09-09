"""Real Pydantic-free, plain-dataclass types -- kept dependency-light
(the SDK's only real, required dependency is `httpx`), mirroring
`api/schemas/public_api.py`'s own real field names exactly."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatResponse:
    message_id: str
    conversation_id: str
    response: str
    citations: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class DocumentUploadResponse:
    document_id: str
    status: str
    name: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResponse:
    results: list[dict]
    total: int
    query: str
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentRunResponse:
    run_id: str
    output: str | None
    conversation_id: str | None
    metadata: dict = field(default_factory=dict)


@dataclass
class UsageResponse:
    period: str
    metrics: list[dict]
    breakdown: list[dict]
    total: int


@dataclass
class AnalyticsResponse:
    period: str
    metrics: list[dict]
    data: list[dict]
    summary: str


@dataclass
class EmbedResponse:
    embedding: list[float]
    model: str
    dimensions: int
