# Python SDK

Full source and README: [`sdks/python/README.md`](../../sdks/python/README.md).

## Install

```bash
pip install -e ./sdks/python  # or, once published: pip install rag-saas-sdk
```

## Usage

```python
from rag_saas_sdk import RagSaasClient

client = RagSaasClient(api_key="pk_...", base_url="https://your-instance.example.com")

response = client.chat.send("What is RAG?", agent_id="agent-1")
print(response.response)

results = client.search.query("chunking strategies", top_k=5)
embedding = client.embed.generate("hello world")
```

Every method maps 1:1 to a real backend endpoint documented at `/docs`
(Swagger UI) on your instance — see [API Reference](../api/OVERVIEW.md).
A non-2xx response raises `RagSaasAPIError(status_code, detail)`; see
[Errors](../api/ERRORS.md) for the error shape it wraps.
