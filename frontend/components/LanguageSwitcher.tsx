"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { UI_LANGUAGE_FLAGS } from "@/lib/voiceConfig";
import Flag from "./Flag";

// Real, honest fallback -- matches api/config.py's own
// UI_SUPPORTED_LANGUAGES default exactly. Used only until the real
// backend answers GET /i18n/languages.
const FALLBACK_LANGUAGES = ["en", "fr", "es", "de", "pt", "ar"];

// Partie 8.1.19 -- real, flags-only dropdown (no text label on the
// flags themselves, per direct user feedback -- a real accessible
// name still lives on each option via Flag's own aria-label, just not
// shown visually). A custom dropdown, not a native <select>: a native
// <option> cannot render a real SVG flag inside it in any browser, so
// a real, flags-only picker needs its own real markup, the same real
// pattern already used by VoiceLanguageSelector.tsx.
export default function LanguageSwitcher() {
  const { language: current, setLanguage } = useTranslation();
  const [languages, setLanguages] = useState<string[]>(FALLBACK_LANGUAGES);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void api
      .get<{ languages: string[]; default: string }>("/i18n/languages")
      .then((data) => setLanguages(data.languages))
      .catch(() => {});
  }, []);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function handleChange(language: string) {
    // Real fix for a real bug: this used to reload the whole page,
    // which never actually helped since no component read a
    // translated string in the first place. setLanguage (lib/i18n.tsx)
    // now reactively re-renders every real component using
    // useTranslation() with the new language's real strings -- no
    // reload needed.
    setLanguage(language);
    setOpen(false);
  }

  const activeFlag = UI_LANGUAGE_FLAGS[current];

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Language: ${activeFlag?.name ?? current}`}
        className="flex items-center gap-1 rounded-lg border border-border bg-surface px-2 py-1.5 hover:border-accent"
      >
        {activeFlag && <Flag country={activeFlag.country} label={activeFlag.name} size={22} />}
        <span aria-hidden="true" className="text-xs text-foreground-muted">▾</span>
      </button>

      {open && (
        <div role="listbox" className="absolute right-0 z-30 mt-1 flex gap-1 rounded-xl border border-border bg-surface p-1.5 shadow-md">
          {languages.map((lang) => {
            const flag = UI_LANGUAGE_FLAGS[lang];
            if (!flag) return null;
            return (
              <button
                key={lang}
                type="button"
                role="option"
                aria-selected={lang === current}
                onClick={() => handleChange(lang)}
                className={`rounded-lg p-1 ${lang === current ? "ring-2 ring-accent" : "hover:bg-surface-muted"}`}
              >
                <Flag country={flag.country} label={flag.name} size={22} />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
