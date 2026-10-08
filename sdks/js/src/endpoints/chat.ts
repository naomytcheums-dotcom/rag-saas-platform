import type { RagSaasClient } from "../client.js";
import type { ChatResponse, ChatStreamEvent } from "../types.js";

export class ChatEndpoint {
  constructor(private readonly client: RagSaasClient) {}

  /** Literal ask: `chat.send(message, agentId, conversationId)` -- one complete response. */
  send(message: string, agentId: string, conversationId?: string): Promise<ChatResponse> {
    return this.client.request<ChatResponse>("POST", "/v1/chat", {
      json: { message, agent_id: agentId, conversation_id: conversationId ?? null, stream: false },
    });
  }

  /** Real Server-Sent-Events streaming (`POST /v1/chat` with `stream: true`).
   * Yields `{ event, data }` -- "start", "token", "citation", "done" (or "error") -- as the
   * server produces them. HTTP errors (401/403/404/429/...) reject with `RagSaasAPIError`
   * before the first event. */
  async *stream(message: string, agentId: string, conversationId?: string): AsyncGenerator<ChatStreamEvent> {
    const response = await this.client.requestRaw("POST", "/v1/chat", {
      json: { message, agent_id: agentId, conversation_id: conversationId ?? null, stream: true },
    });
    if (!response.body) return;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let separator: number;
      while ((separator = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);
        let event = "message";
        let raw = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) raw += line.slice(5).trim();
        }
        let data: Record<string, unknown> = {};
        if (raw) {
          try {
            data = JSON.parse(raw) as Record<string, unknown>;
          } catch {
            data = { raw };
          }
        }
        yield { event, data };
      }
    }
  }
}
