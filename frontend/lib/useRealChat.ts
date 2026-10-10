"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import type { Citation, ConversationMessage } from "@/lib/types";

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

/** Real backend-backed chat, replacing the local-only mock
 * (lib/mockChat.ts) now that login is actually wired up. Uses the
 * authenticated fetch helper because native EventSource cannot send the
 * Authorization header, then parses the SSE wire format by hand. */
export function useRealChat(orgId: string) {
  const { t } = useTranslation();
  const [agentId, setAgentId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initializedFor = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!orgId || initializedFor.current === orgId) return;
    initializedFor.current = orgId;
    void (async () => {
      try {
        const agents = await api.get<AgentSummary[]>(`/organizations/${orgId}/agents`);
        const agent = agents[0];
        if (!agent) {
          setError(t("chat.err_no_agent"));
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
        setError(t("chat.err_load"));
      }
    })();
  }, [orgId, t]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || !agentId || pending) return;
      setError(null);

      const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text, created_at: nowIso() };
      const assistantId = crypto.randomUUID();
      setMessages((prev) => [...prev, userMessage, { id: assistantId, role: "assistant", content: "", created_at: nowIso() }]);
      setPending(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await api.fetchRaw("/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agent_id: agentId, message: text, conversation_id: conversationId }),
          signal: controller.signal,
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
              setError(data.error || t("chat.err_generic"));
            }
          }
        }
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          setError(t("chat.err_connection"));
        }
      } finally {
        setPending(false);
        abortControllerRef.current = null;
      }
      // The messages above carry client-side ids until the server has persisted them. Feedback, follow-up questions and retry address a message by its
      // server id, so adopt the persisted ids of the last user / assistant pair (keeping the citations received on the stream).
      if (conversationId) {
        try {
          const history = await api.get<ConversationMessage[]>(`/conversations/${conversationId}/messages`);
          const lastAssistant = [...history].reverse().find((m) => m.role === "assistant");
          const lastUser = [...history].reverse().find((m) => m.role === "user");
          setMessages((prev) => prev.map((m) => {
            if (m.id === assistantId && lastAssistant) return { ...m, id: lastAssistant.id };
            if (m.id === userMessage.id && lastUser) return { ...m, id: lastUser.id };
            return m;
          }));
        } catch {
          /* the ids stay local; the actions that need a server id will report their own error */
        }
      }
    },
    [agentId, conversationId, pending, t],
  );

  const refresh = useCallback(async () => {
    if (!conversationId) return;
    const history = await api.get<ConversationMessage[]>(`/conversations/${conversationId}/messages`);
    setMessages(history.map((m) => ({ id: m.id, role: m.role, content: m.content, created_at: m.created_at })));
    setError(null);
  }, [conversationId]);

  const stopGeneration = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

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

  return { messages, pending, error, conversationId, sendMessage, editMessage, regenerate, stopGeneration, refresh };
}
