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
