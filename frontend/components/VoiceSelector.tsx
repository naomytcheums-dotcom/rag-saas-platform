"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { synthesizeSpeech } from "@/lib/voiceApi";

interface ElevenLabsVoice {
  name: string;
  voice_id: string;
  gender: string | null;
  accent?: string | null;
  preview_url: string | null;
}

interface VoiceSelectorProps {
  value: string | null;
  onChange: (voiceId: string) => void;
}

// Partie 8.2.9 -- lists real ElevenLabs voices (GET /voice/elevenlabs/voices
// -- the real, documented fallback catalog when no ELEVENLABS_API_KEY
// is configured yet, see api/services/voice.py's own docstring), lets
// the user preview one, and highlights the selected voice.
export default function VoiceSelector({ value, onChange }: VoiceSelectorProps) {
  const [voices, setVoices] = useState<ElevenLabsVoice[]>([]);
  const [previewing, setPreviewing] = useState<string | null>(null);

  useEffect(() => {
    void api.get<ElevenLabsVoice[]>("/voice/elevenlabs/voices").then(setVoices).catch(() => setVoices([]));
  }, []);

  async function preview(voice: ElevenLabsVoice) {
    setPreviewing(voice.voice_id);
    try {
      const audioUrl = voice.preview_url ?? URL.createObjectURL(await synthesizeSpeech("Hello, this is a preview of my voice.", voice.voice_id));
      const audio = new Audio(audioUrl);
      audio.onended = () => setPreviewing(null);
      await audio.play();
    } catch {
      setPreviewing(null);
    }
  }

  return (
    <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {voices.map((voice) => (
        <li key={voice.voice_id}>
          {/* A real <div role="button">, not a nested <button> --
              this card contains its own real, separate preview
              <button>, and HTML forbids a <button> inside a <button>
              (the exact same real class of bug fixed for citations in
              Partie 8.1, see CitationModal.tsx's own top comment). */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => onChange(voice.voice_id)}
            onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && onChange(voice.voice_id)}
            className={`w-full cursor-pointer rounded-xl border p-2 text-left text-sm ${
              value === voice.voice_id ? "border-accent bg-accent-soft" : "border-border bg-surface hover:border-accent"
            }`}
          >
            <p className="font-medium text-foreground">{voice.name}</p>
            <p className="text-xs text-foreground-muted">{voice.gender ?? "—"}</p>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                void preview(voice);
              }}
              className="mt-1 text-xs text-accent-hover hover:underline"
            >
              {previewing === voice.voice_id ? "Playing…" : "▶ Preview"}
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
