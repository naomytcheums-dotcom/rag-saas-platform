"use client";

import { VOICE_LANGUAGES } from "@/lib/voiceConfig";
import Flag from "./Flag";

interface LanguageFlagProps {
  code: string;
  size?: number;
}

// Partie 8.2.6 -- one voice language's real SVG flag (see Flag.tsx's
// own top comment for why this replaced the earlier emoji-based
// version: emoji flags don't render as real images on Windows).
export default function LanguageFlag({ code, size = 20 }: LanguageFlagProps) {
  const language = VOICE_LANGUAGES.find((l) => l.code === code);
  if (!language) return null;
  return <Flag country={language.country} label={language.name} size={size} />;
}
