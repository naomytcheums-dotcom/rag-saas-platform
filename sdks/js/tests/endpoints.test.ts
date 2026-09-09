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
