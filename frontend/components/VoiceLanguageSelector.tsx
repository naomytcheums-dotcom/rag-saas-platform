"use client";

import { useState } from "react";
import { VOICE_LANGUAGES } from "@/lib/voiceConfig";
import LanguageFlag from "./LanguageFlag";

interface VoiceLanguageSelectorProps {
  value: string;
  onChange: (code: string) => void;
}

// Partie 8.2.6 -- a flag per supported voice language; the active one
// is highlighted with a real border + background, matching the light
// theme's own accent color.
export default function VoiceLanguageSelector({ value, onChange }: VoiceLanguageSelectorProps) {
  const [open, setOpen] = useState(false);
  const active = VOICE_LANGUAGES.find((l) => l.code === value) ?? VOICE_LANGUAGES[0];

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2 py-1 text-sm hover:border-accent"
      >
        <LanguageFlag code={active.code} />
        {active.name}
      </button>

      {open && (
        <div className="absolute z-30 mt-1 grid max-h-72 w-48 grid-cols-1 gap-0.5 overflow-y-auto rounded-xl border border-border bg-surface p-1.5 shadow-md">
          {VOICE_LANGUAGES.map((language) => (
            <button
              key={language.code}
              type="button"
              onClick={() => {
                onChange(language.code);
                setOpen(false);
              }}
              className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm ${
                language.code === value ? "border border-accent bg-accent-soft text-accent-hover" : "border border-transparent hover:bg-surface-muted"
              }`}
            >
              <LanguageFlag code={language.code} />
              {language.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
