import { describe, expect, it, vi } from "vitest";
import { RagSaasClient } from "../src/index.js";

function mockFetch(bodyByPath: Record<string, unknown>): typeof fetch {
  return vi.fn(async (url: string | URL) => {
    const path = new URL(url).pathname;
    const body = bodyByPath[path];
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  }) as unknown as typeof fetch;
}

describe("endpoint namespaces", () => {
  it("covers every /v1/* endpoint (documents, search, agents, usage, analytics, embed)", async () => {
    const fetchImpl = mockFetch({
      "/v1/documents": { document_id: "d1", status: "processing", name: "f.pdf", metadata: {} },
      "/v1/search": { results: [], total: 0, query: "q", metadata: {} },
      "/v1/agents/run": { run_id: "r1", output: "done", conversation_id: null, metadata: {} },
      "/v1/usage": { period: "month", metrics: [], breakdown: [], total: 0 },
      "/v1/analytics": { period: "month", metrics: [], data: [], summary: "ok" },
      "/v1/embed": { embedding: [0.1, 0.2], model: "default", dimensions: 2 },
    });
    const client = new RagSaasClient({ apiKey: "pk_test", fetchImpl });

    const doc = await client.documents.upload(new Blob(["content"]), "ws-1");
    expect(doc.document_id).toBe("d1");

    const search = await client.search.query("q");
    expect(search.query).toBe("q");

    const run = await client.agents.run("agent-1", "input");
    expect(run.output).toBe("done");

    const usage = await client.usage.get();
    expect(usage.period).toBe("month");

    const analytics = await client.analytics.get("month", ["tokens"]);
    expect(analytics.summary).toBe("ok");

    const embed = await client.embed.generate("hello");
    expect(embed.dimensions).toBe(2);
  });
});

describe("Hardening Mission, §21/§31 -- streaming + full /v1 coverage", () => {
  function sseResponse(chunks: string[]): Response {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    });
    return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
  }

  it("chat.stream yields real server-sent events, including ones split across network chunks", async () => {
    const fetchImpl = vi.fn(async (_url: string | URL, init?: RequestInit) => {
      expect(JSON.parse(String(init?.body)).stream).toBe(true);
      return sseResponse([
        'event: start\ndata: {}\n\nevent: tok',
        'en\ndata: {"token": "Hel"}\n\n',
        'event: token\ndata: {"token": "lo"}\n\nevent: done\ndata: {}\n\n',
      ]);
    }) as unknown as typeof fetch;
    const client = new RagSaasClient({ apiKey: "pk_test", fetchImpl });

    const events = [];
    for await (const event of client.chat.stream("Hi", "agent-1")) events.push(event);

    expect(events.map((e) => e.event)).toEqual(["start", "token", "token", "done"]);
    expect(events.filter((e) => e.event === "token").map((e) => e.data.token).join("")).toBe("Hello");
  });

  it("chat.stream rejects with RagSaasAPIError before yielding when the server refuses", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "Too many attempts" }), { status: 429, headers: { "Content-Type": "application/json" } }),
    ) as unknown as typeof fetch;
    const client = new RagSaasClient({ apiKey: "pk_test", fetchImpl });

    await expect((async () => { for await (const _ of client.chat.stream("Hi", "agent-1")) { /* never reached */ } })()).rejects.toMatchObject({ statusCode: 429 });
  });

  it("covers the list/create routes that had no SDK method (agents, documents, conversations, knowledge bases)", async () => {
    const seen: string[] = [];
    const fetchImpl = vi.fn(async (url: string | URL, init?: RequestInit) => {
      const u = new URL(url);
      seen.push(`${init?.method} ${u.pathname}?${u.searchParams.toString()}`);
      const body =
        u.pathname === "/v1/conversations" ? { items: [], total: 0, limit: 5, offset: 0 }
        : init?.method === "POST" ? { id: "kb1", name: "KB", description: null, created_at: "2026-01-01T00:00:00Z" }
        : [];
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }) as unknown as typeof fetch;
    const client = new RagSaasClient({ apiKey: "pk_test", fetchImpl });

    await client.agents.list({ limit: 5 });
    await client.documents.list({ offset: 10 });
    await client.knowledgeBases.list();
    const conversations = await client.conversations.list({ limit: 5, agentId: "agent-1" });
    const kb = await client.knowledgeBases.create("KB");

    expect(conversations.total).toBe(0);
    expect(kb.id).toBe("kb1");
    expect(seen).toEqual([
      "GET /v1/agents?limit=5&offset=0",
      "GET /v1/documents?limit=20&offset=10",
      "GET /v1/knowledge-bases?limit=20&offset=0",
      "GET /v1/conversations?limit=5&offset=0&agent_id=agent-1",
      "POST /v1/knowledge-bases?",
    ]);
  });
});
