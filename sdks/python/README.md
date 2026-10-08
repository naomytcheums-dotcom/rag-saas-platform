# rag-saas-sdk (Python)

Official Python SDK for the [RAG SaaS Platform](../../README.md) public API (`/v1/*`, Partie 9.1).

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

# Server-sent events: tokens as they are generated
for event in client.chat.stream("Summarize our refund policy", agent_id="agent-1"):
    if event.event == "token":
        print(event.data["token"], end="", flush=True)

# Listing (every /v1 route has an SDK method)
client.agents.list(limit=20)
client.documents.list()
client.conversations.list(agent_id="agent-1")
client.knowledge_bases.list()
client.knowledge_bases.create("Support KB", description="Public help-center articles")
```

`chat.send()` always returns one complete response; passing `stream=True` to it raises `ValueError` — use `chat.stream()`.

Every method maps 1:1 to a real backend endpoint documented at `/docs` (Swagger UI) on your instance. A non-2xx response raises `RagSaasAPIError(status_code, detail)`.
