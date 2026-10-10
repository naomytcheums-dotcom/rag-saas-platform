"use client";

import { useState } from "react";
import { useTranslation } from "@/lib/i18n";
import AudioPermission from "./AudioPermission";
import PushToTalkButton from "./PushToTalkButton";
import VoiceInput from "./VoiceInput";

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  disabled?: boolean;
  /** Quick prompts shown as small pills under the input (a click sends them). */
  suggestions?: string[];
}

// Real chat input: a dark glass card with a glowing gradient border, the text field, the two real voice inputs (tap to toggle, hold to talk)
// and a send button; Enter (without Shift) sends. Suggestions appear as pills underneath.
export default function ChatComposer({ value, onChange, onSend, disabled, suggestions = [] }: ChatComposerProps) {
  const { t } = useTranslation();
  const [voiceMode, setVoiceMode] = useState<"tap" | "hold">("tap");

  function send() {
    if (!value.trim()) return;
    onSend(value);
    onChange("");
  }

  const append = (text: string) => onChange(value ? `${value} ${text}` : text);

  return (
    <div className="bg-surface px-3 pb-4 pt-2 sm:px-4">
      <div className="mx-auto flex w-full max-w-3xl flex-col">
        <div className="relative flex overflow-hidden rounded-2xl bg-gradient-to-br from-[#7e7e7e] via-[#363636] to-[#363636] p-[1.5px] shadow-[0_12px_40px_rgba(0,0,0,0.18)]">
          <span aria-hidden className="pointer-events-none absolute -left-2.5 -top-2.5 h-[30px] w-[30px] bg-[radial-gradient(ellipse_at_center,#fff,rgba(255,255,255,0.3),rgba(255,255,255,0.1),transparent_60%)] blur-[1px]" />
          <div className="flex w-full flex-col overflow-hidden rounded-[15px] bg-[#0d0d0e]/95">
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
              rows={2}
              disabled={disabled}
              className="h-[72px] max-h-40 w-full resize-none bg-transparent px-4 py-3 text-[15px] text-white outline-none placeholder:text-[#f3f6fd]/70 focus:placeholder:text-[#363636] disabled:opacity-50 [&::-webkit-scrollbar]:w-2.5 [&::-webkit-scrollbar-thumb]:rounded-[5px] [&::-webkit-scrollbar-thumb]:bg-[#888] [&::-webkit-scrollbar-track]:bg-transparent"
            />
            <div className="flex items-end justify-between p-2.5">
              <div className="flex items-center gap-2 text-white/60">
                <div className="flex items-center gap-0.5 rounded-full bg-white/10 p-0.5 text-[11px]">
                  {(["tap", "hold"] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setVoiceMode(mode)}
                      aria-pressed={voiceMode === mode}
                      className={`rounded-full px-2.5 py-1 transition-colors ${voiceMode === mode ? "bg-white/90 text-[#0d0d0e]" : "text-white/70 hover:text-white"}`}
                    >
                      {t(mode)}
                    </button>
                  ))}
                </div>
                <div className="scale-[0.8]">
                  <AudioPermission>{voiceMode === "tap" ? <VoiceInput onTranscript={append} /> : <PushToTalkButton onTranscript={append} />}</AudioPermission>
                </div>
              </div>
              <button
                type="button"
                onClick={send}
                disabled={disabled || !value.trim()}
                aria-label={t("send")}
                className="group flex rounded-[10px] bg-gradient-to-t from-[#292929] via-[#555] to-[#292929] p-0.5 shadow-[inset_0_6px_2px_-4px_rgba(255,255,255,0.5)] transition-all duration-150 active:scale-90 disabled:opacity-50"
              >
                <i className="flex h-[30px] w-[30px] items-center justify-center rounded-[10px] bg-black/10 p-1.5 text-[#8b8b8b] backdrop-blur-[3px] transition-all group-hover:text-[#f3f6fd] group-hover:[filter:drop-shadow(0_0_5px_#fff)] group-focus:rotate-45 group-focus:text-[#f3f6fd]">
                  <svg viewBox="0 0 512 512" aria-hidden className="h-full w-full">
                    <path fill="currentColor" d="M473 39.05a24 24 0 0 0-25.5-5.46L47.47 185h-.08a24 24 0 0 0 1 45.16l.41.13l137.3 58.63a16 16 0 0 0 15.54-3.59L422 80a7.07 7.07 0 0 1 10 10L226.66 310.26a16 16 0 0 0-3.59 15.54l58.65 137.38c.06.2.12.38.19.57c3.2 9.27 11.3 15.81 21.09 16.25h1a24.63 24.63 0 0 0 23-15.46L478.39 64.62A24 24 0 0 0 473 39.05" />
                  </svg>
                </i>
              </button>
            </div>
          </div>
        </div>
        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-3 text-xs text-white">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                disabled={disabled}
                onClick={() => onSend(suggestion)}
                className="select-none rounded-[10px] border-[1.5px] border-[#363636] bg-[#1b1b1b] px-2.5 py-1 transition-colors hover:border-[#ff541f] disabled:opacity-50"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
