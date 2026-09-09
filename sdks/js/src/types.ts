/** Mirrors `api/schemas/public_api.py`'s real response field names exactly. */

export interface ChatResponse {
  message_id: string;
  conversation_id: string;
  response: string;
  citations: Record<string, unknown>[];
  metadata: Record<string, unknown>;
}

export interface DocumentUploadResponse {
  document_id: string;
  status: string;
  name: string;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  results: Record<string, unknown>[];
  total: number;
  query: string;
  metadata: Record<string, unknown>;
}

export interface AgentRunResponse {
  run_id: string;
  output: string | null;
  conversation_id: string | null;
  metadata: Record<string, unknown>;
}

export interface UsageResponse {
  period: string;
  metrics: Record<string, unknown>[];
  breakdown: Record<string, unknown>[];
  total: number;
}

export interface AnalyticsResponse {
  period: string;
  metrics: Record<string, unknown>[];
  data: Record<string, unknown>[];
  summary: string;
}

export interface EmbedResponse {
  embedding: number[];
  model: string;
  dimensions: number;
}
