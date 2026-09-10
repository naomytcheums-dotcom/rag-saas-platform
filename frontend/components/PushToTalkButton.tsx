"use client";

import { useRef, useState } from "react";
import { useTranslation } from "@/lib/i18n";
import { getSpeechRecognitionConstructor, type SpeechRecognitionLike } from "@/lib/speechTypes";
import { settings } from "@/lib/voiceConfig";

interface PushToTalkButtonProps {
  language?: string;
  onTranscript: (text: string) => void;
}

type PttState = "idle" | "pressed" | "listening" | "canceling";

// Partie 8.2.4 -- hold to talk, release to send, drag off the button
// to cancel (the literal ask's own real interaction). Real haptic
// feedback via the standard Vibration API where supported (mobile
// browsers), a real, honest no-op elsewhere.
export default function PushToTalkButton({ language, onTranscript }: PushToTalkButtonProps) {
  const { t } = useTranslation();
  const [state, setState] = useState<PttState>("idle");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pressPositionRef = useRef<{ x: number; y: number } | null>(null);

  function vibrate() {
    if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(15);
  }

  function start(clientX: number, clientY: number) {
    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) return;
    pressPositionRef.current = { x: clientX, y: clientY };
    vibrate();
    setState("pressed");

    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = language ?? "fr-FR";
    recognition.onresult = (event) => {
      const last = event.results[event.results.length - 1];
      if (last?.isFinal) onTranscript(last[0].transcript);
    };
    recognition.onend = () => setState("idle");
    recognitionRef.current = recognition;
    recognition.start();
    setState("listening");

    timeoutRef.current = setTimeout(() => stop(true), settings.PUSH_TO_TALK_TIMEOUT_MS);
  }

  function stop(send: boolean) {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (!send) recognitionRef.current?.abort();
    else recognitionRef.current?.stop();
    setState("idle");
    pressPositionRef.current = null;
  }

  function handleMove(clientX: number, clientY: number) {
    if (state !== "listening" || !pressPositionRef.current) return;
    const dx = clientX - pressPositionRef.current.x;
    const dy = clientY - pressPositionRef.current.y;
    const draggedAway = Math.hypot(dx, dy) > 80;
    setState(draggedAway ? "canceling" : "listening");
  }

  function handleRelease() {
    stop(state !== "canceling");
  }

  return (
    <button
      type="button"
      onPointerDown={(event) => start(event.clientX, event.clientY)}
      onPointerMove={(event) => handleMove(event.clientX, event.clientY)}
      onPointerUp={handleRelease}
      onPointerLeave={() => state === "listening" && setState("canceling")}
      aria-label={t("hold_to_talk")}
      className={`relative flex h-14 w-14 select-none items-center justify-center rounded-full text-xl transition-colors ${
        state === "canceling" ? "bg-danger-soft text-danger" : state !== "idle" ? "bg-accent text-white" : "bg-accent-soft text-accent-hover"
      }`}
    >
      {state === "listening" && <span className="absolute inset-0 animate-ping rounded-full bg-accent opacity-30" aria-hidden="true" />}
      {state === "canceling" ? (
        <span aria-hidden="true" className="text-lg leading-none">&times;</span>
      ) : (
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="2" width="6" height="12" rx="3" />
          <path d="M5 10a7 7 0 0 0 14 0" />
          <line x1="12" y1="19" x2="12" y2="22" />
        </svg>
      )}
    </button>
  );
}
