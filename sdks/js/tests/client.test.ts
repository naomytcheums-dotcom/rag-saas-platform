import { describe, expect, it, vi } from "vitest";
import { RagSaasClient, RagSaasAPIError } from "../src/index.js";

function mockFetch(status: number, body: unknown): typeof fetch {
  return vi.fn(async () =>
    new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    })
  ) as unknown as typeof fetch;
}

describe("RagSaasClient", () => {
  it("sends the API key header and base URL correctly", async () => {
    const fetchImpl = mockFetch(200, { message_id: "m1", conversation_id: "c1", response: "hi", citations: [], metadata: {} });
    const client = new RagSaasClient({ apiKey: "pk_test", baseUrl: "https://test.example.com", fetchImpl });

    await client.chat.send("Hello", "agent-1");

    const [url, init] = (fetchImpl as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("https://test.example.com/v1/chat");
    expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("pk_test");
  });

  it("raises RagSaasAPIError on non-2xx responses", async () => {
    const fetchImpl = mockFetch(401, { detail: "Invalid API key" });
    const client = new RagSaasClient({ apiKey: "bad", fetchImpl });

    await expect(client.chat.send("Hi", "agent-1")).rejects.toBeInstanceOf(RagSaasAPIError);
    await expect(client.chat.send("Hi", "agent-1")).rejects.toMatchObject({ statusCode: 401, detail: "Invalid API key" });
  });

  it("handles a non-JSON error body gracefully", async () => {
    const fetchImpl = mockFetch(500, "internal server error");
    const client = new RagSaasClient({ apiKey: "pk_test", fetchImpl });
    await expect(client.embed.generate("hello")).rejects.toBeInstanceOf(RagSaasAPIError);
  });
});
