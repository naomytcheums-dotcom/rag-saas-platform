# rag-saas-sdk (JavaScript/TypeScript)

Official JS/TS SDK for the RAG SaaS Platform public API (`/v1/*`, Partie 9.1). Zero runtime dependencies -- uses the platform `fetch`.

## Install

```bash
npm install rag-saas-sdk
```

## Usage

```typescript
import { RagSaasClient } from "rag-saas-sdk";

const client = new RagSaasClient({ apiKey: "pk_...", baseUrl: "https://your-instance.example.com" });

const response = await client.chat.send("What is RAG?", "agent-1");
console.log(response.response);

const results = await client.search.query("chunking strategies", undefined, undefined, 5);
const embedding = await client.embed.generate("hello world");
```

Every method maps 1:1 to a real backend endpoint documented at `/docs` (Swagger UI) on your instance. A non-2xx response throws `RagSaasAPIError` (`statusCode`, `detail`).

## Development

```bash
npm install
npm run build
npm test
```

## Streaming and listing

```ts
for await (const event of client.chat.stream("Summarize our refund policy", "agent-1")) {
  if (event.event === "token") process.stdout.write(String(event.data.token));
}

await client.agents.list({ limit: 20 });
await client.documents.list();
await client.conversations.list({ agentId: "agent-1" });
await client.knowledgeBases.list();
await client.knowledgeBases.create("Support KB", "Public help-center articles");
```

`chat.send()` returns one complete response; `chat.stream()` is an async generator and rejects with `RagSaasAPIError` before the first event on an HTTP error.
