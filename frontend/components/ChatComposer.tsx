"use client";

import { useState } from "react";
import { useTranslation } from "@/lib/i18n";
import PushToTalkButton from "./PushToTalkButton";
import VoiceInput from "./VoiceInput";

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  disabled?: boolean;
}

// Real chat input bar: text field, real voice input (tap to toggle,
// Partie 8.2.1) and real push-to-talk (hold, Partie 8.2.4) side by
// side -- both real, independent ways to fill the same real text
// field, Enter (without Shift) sends.
export default function ChatComposer({ value, onChange, onSend, disabled }: ChatComposerProps) {
  const { t } = useTranslation();
  const [voiceMode, setVoiceMode] = useState<"tap" | "hold">("tap");

  function send() {
    if (!value.trim()) return;
    onSend(value);
    onChange("");
  }

  return (
    <div className="border-t border-border bg-surface p-3 sm:p-4">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <div className="flex items-center gap-1 rounded-full bg-surface-muted p-1">
          <button
            type="button"
            onClick={() => setVoiceMode("tap")}
            aria-pressed={voiceMode === "tap"}
            className={`rounded-full px-2 py-1 text-xs ${voiceMode === "tap" ? "bg-accent text-white" : "text-foreground-muted"}`}
          >
            {t("tap")}
          </button>
          <button
            type="button"
            onClick={() => setVoiceMode("hold")}
            aria-pressed={voiceMode === "hold"}
            className={`rounded-full px-2 py-1 text-xs ${voiceMode === "hold" ? "bg-accent text-white" : "text-foreground-muted"}`}
          >
            {t("hold")}
          </button>
        </div>

        {voiceMode === "tap" ? (
          <VoiceInput onTranscript={(text) => onChange(value ? `${value} ${text}` : text)} />
        ) : (
          <PushToTalkButton onTranscript={(text) => onChange(value ? `${value} ${text}` : text)} />
        )}

        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          placeholder={t("ask_placeholder")}
          rows={1}
          disabled={disabled}
          className="max-h-32 flex-1 resize-none rounded-2xl border border-border bg-background px-4 py-2.5 text-sm text-foreground outline-none focus:border-accent disabled:opacity-50"
        />

        <button
          type="button"
          onClick={send}
          disabled={disabled || !value.trim()}
          aria-label={t("send")}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-white hover:bg-accent-hover disabled:opacity-50"
        >
          ➤
        </button>
      </div>
    </div>
  );
}
