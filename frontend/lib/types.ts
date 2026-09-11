// Shared TypeScript types mirroring the FastAPI backend's own real
// Pydantic schemas (api/schemas/*.py). Kept close to the real backend
// field names/shapes so a change on one side is easy to spot on the
// other -- not a hand-wavy approximation.

export interface Conversation {
  id: string;
  agent_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  archived: boolean;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_calls: unknown[] | null;
  tool_call_id: string | null;
  created_at: string;
}

export interface Citation {
  id: string;
  citation_number: number;
  document_id: string;
  document_title?: string;
  page?: number | null;
  url?: string | null;
  exact_passage: string;
  relevance_label?: string | null;
  relevance_score?: number | null;
  chunk_id?: string;
}

export interface MessageFeedback {
  id: string;
  message_id: string;
  user_id: string;
  rating: "positive" | "negative";
  reason: string | null;
  comment: string | null;
  created_at: string;
}

export interface EditHistoryEntry {
  id: string;
  message_id: string;
  version: number;
  content: string;
  edited_at: string;
  edited_by: string | null;
}

export interface ConversationShare {
  id: string;
  conversation_id: string;
  token: string;
  shared_by: string;
  expires_at: string | null;
  max_views: number | null;
  views: number;
  created_at: string;
}

export interface FollowUpQuestion {
  id: string;
  message_id: string;
  question: string;
  clicked: boolean;
  created_at: string;
}

export interface ConversationStats {
  total_conversations: number;
  archived_conversations: number;
  total_messages: number;
}

export interface SearchResult {
  conversation: Conversation;
  matched_message: ConversationMessage | null;
  highlighted_snippet: string | null;
}

// Partie 15.1/15.2 -- universal inbound integrations (Zapier/Make/n8n/
// any webhook-capable CRM), api/schemas/integrations_universal.py.
export interface UniversalConnection {
  id: string;
  name: string;
  provider: string;
  action: string;
  is_active: boolean;
  created_at: string;
  token?: string; // only present in the create-response, shown once
}

export interface IntegrationMapping {
  id: string;
  source_field: string;
  target_field: string;
  transform: string | null;
}

export interface IntegrationLog {
  id: string;
  status: "accepted" | "rejected" | "error";
  payload: Record<string, unknown>;
  detail: string | null;
  created_at: string;
}

export interface ConnectionTestResult {
  connection_active: boolean;
  sample_payload: Record<string, unknown>;
  mapped_payload: Record<string, unknown>;
  would_run_action: string;
}

// Partie 16 (ter) -- plugin marketplace, api/schemas/plugins.py.
export type PluginCategory = "analytics" | "automation" | "communication" | "data" | "integration" | "productivity" | "security" | "other";

export interface Plugin {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string;
  category: PluginCategory;
  manifest: { name: string; version: string; entry_point: string; description: string; permissions: string[]; hooks?: string[] };
  version: string;
  code_size_bytes: number;
  status: "pending" | "approved" | "rejected" | "suspended";
  rejection_reason: string | null;
  install_count: number;
  created_at: string;
  updated_at: string;
}

export interface PluginVersion {
  id: string;
  plugin_id: string;
  version: string;
  manifest: Plugin["manifest"];
  code_size_bytes: number;
  changelog: string | null;
  created_at: string;
}

export interface PluginExecution {
  id: string;
  plugin_id: string;
  organization_id: string;
  installation_id: string | null;
  hook: string | null;
  status: "success" | "error" | "timeout";
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown> | null;
  error_message: string | null;
  duration_ms: number | null;
  created_at: string;
}

export interface PluginInstallation {
  id: string;
  plugin_id: string;
  organization_id: string;
  enabled: boolean;
  config: Record<string, unknown>;
  installed_at: string;
}

export interface PluginReview {
  id: string;
  plugin_id: string;
  organization_id: string;
  user_id: string;
  rating: number;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface PluginRatingSummary {
  average_rating: number | null;
  review_count: number;
}

export interface PluginPermission {
  id: string;
  label: string;
}
