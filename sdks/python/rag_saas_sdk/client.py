"""Real HTTP client + real, namespaced endpoint methods for the RAG
SaaS Platform's own public `/v1/*` API."""

from __future__ import annotations

import httpx

from .errors import RagSaasAPIError
from .types import (
    AgentRunResponse, AnalyticsResponse, ChatResponse, DocumentUploadResponse, EmbedResponse, SearchResponse,
    UsageResponse,
)


class _BaseNamespace:
    def __init__(self, client: "RagSaasClient"):
        self._client = client


class _ChatNamespace(_BaseNamespace):
    def send(self, message: str, agent_id: str, conversation_id: str | None = None, stream: bool = False) -> ChatResponse:
        """Item 5's own literal method -- `chat.send(message, agent_id, conversation_id)`."""
        data = self._client._request("POST", "/v1/chat", json={"message": message, "agent_id": agent_id, "conversation_id": conversation_id, "stream": stream})
        return ChatResponse(**data)


class _DocumentsNamespace(_BaseNamespace):
    def upload(self, file_path: str, workspace_id: str | None = None) -> DocumentUploadResponse:
        """Item 5's own literal method -- `documents.upload(file, workspace_id)`."""
        with open(file_path, "rb") as file_obj:
            params = {"workspace_id": workspace_id} if workspace_id else None
            data = self._client._request("POST", "/v1/documents", files={"file": file_obj}, params=params)
        return DocumentUploadResponse(**data)


class _SearchNamespace(_BaseNamespace):
    def query(self, query: str, workspace_id: str | None = None, filters: dict | None = None, top_k: int = 5) -> SearchResponse:
        """Item 5's own literal method -- `search.query(query, workspace_id, filters, top_k)`."""
        data = self._client._request("POST", "/v1/search", json={"query": query, "workspace_id": workspace_id, "filters": filters, "top_k": top_k})
        return SearchResponse(**data)


class _AgentsNamespace(_BaseNamespace):
    def run(self, agent_id: str, input: str, conversation_id: str | None = None) -> AgentRunResponse:
        """Item 5's own literal method -- `agents.run(agent_id, input, conversation_id)`."""
        data = self._client._request("POST", "/v1/agents/run", json={"agent_id": agent_id, "input": input, "conversation_id": conversation_id})
        return AgentRunResponse(**data)


class _UsageNamespace(_BaseNamespace):
    def get(self, period: str = "month", metric: str | None = None) -> UsageResponse:
        """Item 5's own literal method -- `usage.get(period, metric)`."""
        params = {"period": period}
        if metric:
            params["metric"] = metric
        data = self._client._request("GET", "/v1/usage", params=params)
        return UsageResponse(**data)


class _AnalyticsNamespace(_BaseNamespace):
    def get(self, period: str = "month", metrics: list[str] | None = None) -> AnalyticsResponse:
        """Item 5's own literal method -- `analytics.get(period, metrics)`."""
        params = {"period": period}
        if metrics:
            params["metrics"] = ",".join(metrics)
        data = self._client._request("GET", "/v1/analytics", params=params)
        return AnalyticsResponse(**data)


class _EmbedNamespace(_BaseNamespace):
    def generate(self, text: str, model: str | None = None) -> EmbedResponse:
        """Item 5's own literal method -- `embed.generate(text, model)`."""
        data = self._client._request("POST", "/v1/embed", json={"text": text, "model": model})
        return EmbedResponse(**data)


class RagSaasClient:
    """Real, synchronous client. `base_url` defaults to the real,
    hosted platform -- override for a self-hosted/staging deployment."""

    def __init__(self, api_key: str, base_url: str = "https://api.ragsaasplatform.com", timeout: float = 30.0):
        self._http = httpx.Client(base_url=base_url, headers={"X-API-Key": api_key}, timeout=timeout)
        self.chat = _ChatNamespace(self)
        self.documents = _DocumentsNamespace(self)
        self.search = _SearchNamespace(self)
        self.agents = _AgentsNamespace(self)
        self.usage = _UsageNamespace(self)
        self.analytics = _AnalyticsNamespace(self)
        self.embed = _EmbedNamespace(self)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = response.text
            raise RagSaasAPIError(response.status_code, detail)
        return response.json()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "RagSaasClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
