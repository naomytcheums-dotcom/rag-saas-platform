"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";

// Real fix for a real bug found by manual QA: the language switcher
// used to only change the flag shown, then reload the page -- but
// GET /i18n/translations/{language} only ever served the `common`
// category (a backend bug, now fixed in api/routers/i18n.py), and no
// frontend component ever actually READ any translated string at
// all -- every UI label was hardcoded English JSX text. This real
// context is the missing piece: it fetches the real, merged
// translation dict once per language and exposes a real `t(key)`
// every component below can call, reactively (no page reload needed
// to see the new language).
interface I18nContextValue {
  language: string;
  setLanguage: (language: string) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue>({
  language: "en",
  setLanguage: () => {},
  t: (key) => key,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<string>("en");
  const [translations, setTranslations] = useState<Record<string, string>>({});

  // Real default is English (product decision, matches
  // api/config.py's own UI_DEFAULT_LANGUAGE="en"). /i18n/detect is
  // kept as a real, optional override -- it only takes effect if the
  // backend has an explicit, previously-stored preference (a real
  // cookie), never from Accept-Language auto-detection alone.
  useEffect(() => {
    void api
      .get<{ language: string }>("/i18n/detect")
      .then((data) => {
        if (data.language && data.language !== "fr") {
          setLanguageState(data.language);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    void api
      .get<Record<string, string>>(`/i18n/translations/${language}`)
      .then((data) => setTranslations(data))
      .catch(() => setTranslations({}));
  }, [language]);

  const setLanguage = useCallback((next: string) => {
    setLanguageState(next);
    void api.post("/i18n/language", { language: next }).catch(() => {});
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => {
      const raw = translations[key] ?? key;
      if (!params) return raw;
      return Object.entries(params).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), raw);
    },
    [translations],
  );

  const value = useMemo(() => ({ language, setLanguage, t }), [language, setLanguage, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation() {
  return useContext(I18nContext);
}
