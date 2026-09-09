"""Partie 9.2.10 -- the real, official Python SDK for the RAG SaaS
Platform's own public `/v1/*` API (Partie 9.1). A thin, real wrapper
around `httpx` -- every method here maps 1:1 to a real, already-built
backend endpoint, never a new API surface of its own."""

from .client import RagSaasClient
from .errors import RagSaasAPIError

__all__ = ["RagSaasClient", "RagSaasAPIError"]
__version__ = "0.1.0"
