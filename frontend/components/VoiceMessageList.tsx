"use client";

import { useEffect, useState } from "react";
import { api, fileUrl } from "@/lib/api";

interface VoiceMessage {
  id: string;
  type: string;
  transcription: string | null;
  duration_ms: number;
  language: string | null;
  created_at: string;
}

interface VoiceMessageListProps {
  conversationId: string;
}

// Partie 8.2.7 -- real voice-message history: transcription, a real
// <audio> player streaming from GET /voice-messages/{id}/audio, and
// duration.
export default function VoiceMessageList({ conversationId }: VoiceMessageListProps) {
  const [messages, setMessages] = useState<VoiceMessage[]>([]);

  useEffect(() => {
    void api
      .get<VoiceMessage[]>(`/conversations/${conversationId}/voice-messages`)
      .then(setMessages)
      .catch(() => setMessages([]));
  }, [conversationId]);

  if (messages.length === 0) return <p className="text-sm text-foreground-muted">No voice messages yet.</p>;

  return (
    <ul className="space-y-2">
      {messages.map((message) => (
        <li key={message.id} className="rounded-xl border border-border bg-surface p-3">
          <div className="flex items-center justify-between text-xs text-foreground-muted">
            <span className="font-medium text-foreground">{message.type === "user" ? "You" : "Assistant"}</span>
            <span>{(message.duration_ms / 1000).toFixed(1)}s</span>
          </div>
          {message.transcription && <p className="mt-1 text-sm text-foreground">{message.transcription}</p>}
          <audio controls className="mt-2 h-8 w-full" src={fileUrl(`/voice-messages/${message.id}/audio`)} />
        </li>
      ))}
    </ul>
  );
}
