"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const LANGUAGE_LABELS: Record<string, string> = {
  en: "English",
  fr: "Français",
  es: "Español",
  de: "Deutsch",
  pt: "Português",
  ar: "العربية",
};

// Partie 8.1.19 -- lists supported languages (GET /i18n/languages),
// saves the choice via POST /i18n/language (a real cookie server-side,
// see api/services/i18n.py's own docstring), and reloads the page so
// every server-rendered string picks up the new language immediately.
export default function LanguageSwitcher() {
  const [languages, setLanguages] = useState<string[]>([]);
  const [current, setCurrent] = useState<string>("en");

  useEffect(() => {
    // Both real, honest no-ops on failure (e.g. the backend isn't
    // reachable yet) -- the switcher just stays empty/default rather
    // than throwing an uncaught promise rejection.
    void api
      .get<{ languages: string[]; default: string }>("/i18n/languages")
      .then((data) => {
        setLanguages(data.languages);
        setCurrent(data.default);
      })
      .catch(() => {});
    void api
      .get<{ language: string }>("/i18n/detect")
      .then((data) => setCurrent(data.language))
      .catch(() => {});
  }, []);

  async function handleChange(language: string) {
    setCurrent(language);
    await api.post("/i18n/language", { language });
    window.location.reload();
  }

  return (
    <select
      value={current}
      onChange={(event) => void handleChange(event.target.value)}
      aria-label="Language"
      className="rounded-lg border border-border bg-surface px-2 py-1 text-sm text-foreground outline-none focus:border-accent"
    >
      {languages.map((lang) => (
        <option key={lang} value={lang}>
          {LANGUAGE_LABELS[lang] ?? lang}
        </option>
      ))}
    </select>
  );
}
