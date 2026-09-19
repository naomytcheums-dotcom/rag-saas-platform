"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Citation, ConversationMessage } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ChatMessage extends Pick<ConversationMessage, "id" | "role" | "content" | "created_at"> {
  citations?: Citation[];
}

interface AgentSummary {
  id: string;
  name: string;
}

function nowIso(): string {
  return new Date().toISOString();
}

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("access_token");
}

/** Real backend-backed chat, replacing the local-only mock
 * (lib/mockChat.ts) now that login is actually wired up. Uses
 * POST /chat/stream directly (not the native EventSource, which can't
 * send the Authorization header this API requires) and parses the SSE
 * wire format by hand: `event: <type>\ndata: <json>\n\n`. */
export function useRealChat(orgId: string) {
  const [agentId, setAgentId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initializedFor = useRef<string | null>(null);

  useEffect(() => {
    if (!orgId || initializedFor.current === orgId) return;
    initializedFor.current = orgId;
    void (async () => {
      try {
        const agents = await api.get<AgentSummary[]>(`/organizations/${orgId}/agents`);
        const agent = agents[0];
        if (!agent) {
          setError("Aucun agent n'existe encore pour cette organisation. Créez-en un dans Agents.");
          return;
        }
        setAgentId(agent.id);

        const existing = await api.get<{ id: string }[]>(`/conversations?agent_id=${agent.id}&limit=1`);
        let convId = existing[0]?.id ?? null;
        if (!convId) {
          const created = await api.post<{ id: string }>("/conversations", {
            agent_id: agent.id, organization_id: orgId, title: "Nouvelle conversation",
          });
          convId = created.id;
        }
        setConversationId(convId);

        const history = await api.get<ConversationMessage[]>(`/conversations/${convId}/messages`);
        setMessages(history.map((m) => ({ id: m.id, role: m.role, content: m.content, created_at: m.created_at })));
      } catch (err) {
         
        console.error("useRealChat init failed:", err);
        setError("Impossible de charger la conversation.");
      }
    })();
  }, [orgId]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || !agentId || pending) return;
      setError(null);

      const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text, created_at: nowIso() };
      const assistantId = crypto.randomUUID();
      setMessages((prev) => [...prev, userMessage, { id: assistantId, role: "assistant", content: "", created_at: nowIso() }]);
      setPending(true);

      try {
        const token = getAccessToken();
        const response = await fetch(`${API_BASE_URL}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          credentials: "include",
          body: JSON.stringify({ agent_id: agentId, message: text, conversation_id: conversationId }),
        });
        if (!response.ok || !response.body) throw new Error(`Chat stream failed (${response.status})`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        const citations: Citation[] = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let sepIndex: number;
          while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
            const rawEvent = buffer.slice(0, sepIndex);
            buffer = buffer.slice(sepIndex + 2);
            if (!rawEvent.trim() || rawEvent.startsWith(":")) continue;

            const eventLine = rawEvent.split("\n").find((line) => line.startsWith("event:"));
            const dataLine = rawEvent.split("\n").find((line) => line.startsWith("data:"));
            if (!eventLine || !dataLine) continue;
            const type = eventLine.slice(6).trim();
            const data = JSON.parse(dataLine.slice(5).trim());

            if (type === "token") {
              setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + data.token } : m)));
            } else if (type === "citation") {
              citations.push({
                id: data.id, citation_number: data.citation_number, document_id: data.id, document_title: data.source_title,
                url: data.source_url, exact_passage: data.text, relevance_score: data.relevance_score,
              });
              setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, citations: [...citations] } : m)));
            } else if (type === "error") {
              setError(data.error || "Une erreur est survenue.");
            }
          }
        }
      } catch {
        setError("La connexion au serveur de chat a échoué.");
      } finally {
        setPending(false);
      }
    },
    [agentId, conversationId, pending],
  );

  const editMessage = useCallback(
    (id: string, newContent: string) => {
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content: newContent } : m)));
      void sendMessage(newContent);
    },
    [sendMessage],
  );

  const regenerate = useCallback(
    (id: string) => {
      const index = messages.findIndex((m) => m.id === id);
      const precedingUser = [...messages.slice(0, index === -1 ? messages.length : index + 1)]
        .reverse()
        .find((m) => m.role === "user");
      if (precedingUser) void sendMessage(precedingUser.content);
    },
    [messages, sendMessage],
  );

  return { messages, pending, error, sendMessage, editMessage, regenerate };
}
