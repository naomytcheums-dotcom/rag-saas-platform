"use client";

import { useEffect, useRef, useState } from "react";
import { getSpeechRecognitionConstructor, type SpeechRecognitionLike } from "@/lib/speechTypes";
import { settings } from "@/lib/voiceConfig";
import { classifyVoiceError, logVoiceError, type VoiceErrorType } from "@/lib/voiceErrors";
import VoiceError from "./VoiceError";

interface VoiceInputProps {
  language?: string;
  onTranscript: (text: string) => void;
}

type VoiceInputState = "idle" | "listening" | "processing";

// Partie 8.2.1 -- real speech recognition via the browser's own Web
// Speech API (this project's own real, free default STT provider --
// see api/services/voice.py's own top docstring for why the other,
// paid providers have no client-side component: they need a real
// server round trip through /voice/stt instead, wired up separately).
export default function VoiceInput({ language, onTranscript }: VoiceInputProps) {
  const [state, setState] = useState<VoiceInputState>("idle");
  const [interimText, setInterimText] = useState("");
  const [error, setError] = useState<VoiceErrorType | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => () => recognitionRef.current?.abort(), []);

  function startListening() {
    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) {
      setError("unknown");
      return;
    }

    const recognition = new Recognition();
    recognition.continuous = settings.STT_CONTINUOUS;
    recognition.interimResults = settings.STT_INTERIM_RESULTS;
    recognition.maxAlternatives = settings.STT_MAX_ALTERNATIVES;
    recognition.lang = language ?? "fr-FR";

    recognition.onresult = (event) => {
      let finalText = "";
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) finalText += result[0].transcript;
        else interim += result[0].transcript;
      }
      setInterimText(interim);
      if (finalText) {
        setState("processing");
        onTranscript(finalText);
      }
    };

    recognition.onerror = (event) => {
      logVoiceError(event, "VoiceInput");
      setError(classifyVoiceError(new DOMException(event.message ?? "", event.error)));
      setState("idle");
    };

    recognition.onend = () => {
      setState("idle");
      setInterimText("");
    };

    recognitionRef.current = recognition;
    setError(null);
    setState("listening");
    recognition.start();
  }

  function stopListening() {
    recognitionRef.current?.stop();
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={state === "listening" ? stopListening : startListening}
        disabled={state === "processing"}
        aria-pressed={state === "listening"}
        aria-label={state === "listening" ? "Stop listening" : "Start voice input"}
        className={`relative flex h-11 w-11 items-center justify-center rounded-full transition-colors ${
          state === "listening" ? "bg-accent text-white" : "bg-accent-soft text-accent-hover hover:bg-accent hover:text-white"
        }`}
      >
        {state === "listening" && (
          <span className="absolute inset-0 animate-ping rounded-full bg-accent opacity-40" aria-hidden="true" />
        )}
        <span className="relative" aria-hidden="true">
          {state === "processing" ? (
            "…"
          ) : (
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="2" width="6" height="12" rx="3" />
              <path d="M5 10a7 7 0 0 0 14 0" />
              <line x1="12" y1="19" x2="12" y2="22" />
            </svg>
          )}
        </span>
      </button>

      {interimText && <p className="text-sm italic text-foreground-muted">{interimText}</p>}
      {error && <VoiceError type={error} onRetry={startListening} />}
    </div>
  );
}
