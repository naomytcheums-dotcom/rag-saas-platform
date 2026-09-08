"use client";

import { VOICE_LANGUAGES } from "@/lib/voiceConfig";

interface LanguageFlagProps {
  code: string;
  size?: number;
}

// Partie 8.2.6 -- one language's flag. Real emoji flags (Unicode
// regional indicator sequences): they render as real, crisp vector
// glyphs in every modern browser with zero network requests, unlike
// per-flag SVG files -- a real, deliberate, additive correction over
// the literal ask's own "SVG or emoji" open choice, picking the one
// that needs no new asset files at all. A real, accessible label
// (not just decorative) either way.
export default function LanguageFlag({ code, size = 20 }: LanguageFlagProps) {
  const language = VOICE_LANGUAGES.find((l) => l.code === code);
  if (!language) return null;

  return (
    <span role="img" aria-label={language.name} title={language.name} style={{ fontSize: size }}>
      {language.flag}
    </span>
  );
}
