"use client";

import { useTranslation } from "@/lib/i18n";

const LANGUAGES: { code: string; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "fr", label: "FR" },
];

// Real language switcher, wired to the real i18n context
// (lib/i18n.tsx) -- that context already had a working
// setLanguage()/POST /i18n/language round trip, but no component ever
// actually called it, so there was no real way for a visitor to change
// language before this. Limited to the 2 languages this product
// targets (see docs/developer/I18N.md); backend enforcement lives in
// api/config.py's UI_SUPPORTED_LANGUAGES, this list only needs to stay
// in sync with it for the UI, not duplicate the source of truth.
export default function LanguageSelector() {
  const { language, setLanguage } = useTranslation();

  return (
    <div className="flex items-center gap-1 text-xs">
      {LANGUAGES.map((lang) => (
        <button
          key={lang.code}
          type="button"
          onClick={() => setLanguage(lang.code)}
          aria-pressed={language === lang.code}
          className={`rounded-md px-2 py-1 font-medium transition-colors ${
            language === lang.code ? "bg-accent-soft text-accent-hover" : "text-foreground-muted hover:bg-surface-muted"
          }`}
        >
          {lang.label}
        </button>
      ))}
    </div>
  );
}
