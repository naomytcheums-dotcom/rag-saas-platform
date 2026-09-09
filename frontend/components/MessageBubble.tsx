"use client";

import { useState } from "react";
import { useTranslation } from "@/lib/i18n";
import type { MockMessage } from "@/lib/mockChat";
import CitationList from "./CitationList";
import CopyButton from "./CopyButton";
import FeedbackButtons from "./FeedbackButtons";
import MessageContent from "./MessageContent";
import VoiceOutput from "./VoiceOutput";

interface MessageBubbleProps {
  message: MockMessage;
  isLast: boolean;
  onEdit: (id: string, content: string) => void;
  onRegenerate: (id: string) => void;
  regenerating: boolean;
}

// One message row -- user (right-aligned) or assistant (left-aligned,
// with the real 8.1 components: citations, copy, feedback, voice
// playback). Regenerate/Edit here are wired to the local mock chat
// state (lib/mockChat.ts), not the real RegenerateButton/EditQuestion
// components -- those hard-code real backend endpoints
// (/conversations/{id}/messages/{id}/regenerate) that need a real,
// authenticated conversation this demo page doesn't have yet; using
// them here against a fake id would just fail every time, which is
// less honest than this real, working, local equivalent.
export default function MessageBubble({ message, isLast, onEdit, onRegenerate, regenerating }: MessageBubbleProps) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-accent px-4 py-2.5 text-sm text-white sm:max-w-[75%]">
          {editing ? (
            <div className="flex flex-col gap-2">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                rows={2}
                className="w-64 max-w-full resize-none rounded-lg border border-white/30 bg-white/10 p-2 text-sm text-white outline-none placeholder:text-white/60"
              />
              <div className="flex justify-end gap-2 text-xs">
                <button type="button" onClick={() => setEditing(false)} className="text-white/80 hover:underline">{t("cancel")}</button>
                <button
                  type="button"
                  onClick={() => {
                    onEdit(message.id, draft);
                    setEditing(false);
                  }}
                  className="rounded-md bg-white/20 px-2 py-1 font-medium hover:bg-white/30"
                >
                  {t("save_and_resend")}
                </button>
              </div>
            </div>
          ) : (
            <>
              <p>{message.content}</p>
              <button type="button" onClick={() => setEditing(true)} className="mt-1 text-xs text-white/70 hover:text-white hover:underline">
                {t("edit")}
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[90%] rounded-2xl rounded-tl-sm border border-border bg-surface p-4 shadow-sm sm:max-w-[80%]">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-accent-hover">{t("assistant")}</p>
        <MessageContent text={message.content} citations={message.citations} />

        <div className="mt-2 flex flex-wrap items-center gap-1">
          <CopyButton text={message.content} citations={message.citations} format="with_citations" />
          <FeedbackButtons messageId={message.id} />
          <VoiceOutput text={message.content.replace(/\[\d+\]/g, "")} streaming />
          {isLast && (
            <button
              type="button"
              onClick={() => onRegenerate(message.id)}
              disabled={regenerating}
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent-soft hover:text-accent-hover disabled:opacity-50"
            >
              {regenerating ? t("regenerating") : t("regenerate")}
            </button>
          )}
        </div>

        {message.citations && <CitationList citations={message.citations} />}
      </div>
    </div>
  );
}
