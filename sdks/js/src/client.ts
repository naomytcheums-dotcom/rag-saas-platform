import { RagSaasAPIError } from "./errors.js";
import { ChatEndpoint } from "./endpoints/chat.js";
import { DocumentsEndpoint } from "./endpoints/documents.js";
import { SearchEndpoint } from "./endpoints/search.js";
import { AgentsEndpoint } from "./endpoints/agents.js";
import { UsageEndpoint } from "./endpoints/usage.js";
import { AnalyticsEndpoint } from "./endpoints/analytics.js";
import { EmbedEndpoint } from "./endpoints/embed.js";

export interface RagSaasClientOptions {
  apiKey: string;
  baseUrl?: string;
  timeoutMs?: number;
  /** Injectable for tests; defaults to the global `fetch`. */
  fetchImpl?: typeof fetch;
}

/** Real HTTP client -- every namespace method maps 1:1 to a real
 * backend `/v1/*` endpoint (see `api/routers/public_api.py`). */
export class RagSaasClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  readonly chat: ChatEndpoint;
  readonly documents: DocumentsEndpoint;
  readonly search: SearchEndpoint;
  readonly agents: AgentsEndpoint;
  readonly usage: UsageEndpoint;
  readonly analytics: AnalyticsEndpoint;
  readonly embed: EmbedEndpoint;

  constructor(options: RagSaasClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl ?? "https://api.ragsaasplatform.com").replace(/\/$/, "");
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this.fetchImpl = options.fetchImpl ?? fetch;

    this.chat = new ChatEndpoint(this);
    this.documents = new DocumentsEndpoint(this);
    this.search = new SearchEndpoint(this);
    this.agents = new AgentsEndpoint(this);
    this.usage = new UsageEndpoint(this);
    this.analytics = new AnalyticsEndpoint(this);
    this.embed = new EmbedEndpoint(this);
  }

  async request<T>(method: string, path: string, options: { json?: unknown; params?: Record<string, string | undefined>; body?: FormData } = {}): Promise<T> {
    const url = new URL(this.baseUrl + path);
    if (options.params) {
      for (const [key, value] of Object.entries(options.params)) {
        if (value !== undefined) url.searchParams.set(key, value);
      }
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await this.fetchImpl(url.toString(), {
        method,
        headers: {
          "X-API-Key": this.apiKey,
          ...(options.json ? { "Content-Type": "application/json" } : {}),
        },
        body: options.json ? JSON.stringify(options.json) : options.body,
        signal: controller.signal,
      });

      if (!response.ok) {
        let detail: unknown;
        try {
          const parsed = await response.clone().json();
          detail = parsed?.detail ?? parsed;
        } catch {
          detail = await response.text();
        }
        throw new RagSaasAPIError(response.status, detail);
      }

      return (await response.json()) as T;
    } finally {
      clearTimeout(timeout);
    }
  }
}
