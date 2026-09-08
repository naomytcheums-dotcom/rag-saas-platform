"use client";

import { useRef, useState } from "react";
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
      aria-label="Hold to talk"
      className={`relative flex h-14 w-14 select-none items-center justify-center rounded-full text-xl transition-colors ${
        state === "canceling" ? "bg-danger-soft text-danger" : state !== "idle" ? "bg-accent text-white" : "bg-accent-soft text-accent-hover"
      }`}
    >
      {state === "listening" && <span className="absolute inset-0 animate-ping rounded-full bg-accent opacity-30" aria-hidden="true" />}
      <span aria-hidden="true">{state === "canceling" ? "✕" : "🎙"}</span>
    </button>
  );
}
