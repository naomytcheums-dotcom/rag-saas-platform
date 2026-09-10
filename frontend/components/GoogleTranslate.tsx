"use client";

import { useEffect, useRef, useState } from "react";
import { UI_LANGUAGE_FLAGS } from "@/lib/voiceConfig";
import Flag from "./Flag";

// Replaces the old per-string i18n dictionary (lib/i18n.tsx) as the
// site-wide translator, per direct user feedback: the dictionary only
// covered components that explicitly called useTranslation(), so most
// pages never visibly changed language. Google's website-translate
// widget translates the whole rendered DOM instead, so every page
// benefits immediately, no per-string wiring needed.
//
// Google's own widget UI (the top banner iframe, the plain <select>)
// is hidden entirely -- real, direct user feedback: it looked bolted-on
// and broke the page layout. Only Google's underlying hidden <select>
// is kept (in the DOM, never visible); this component drives it from
// a custom flags dropdown matching the rest of this app's design, the
// same pattern the old LanguageSwitcher used for the abandoned i18n
// dictionary.
const SUPPORTED_LANGUAGES = Object.keys(UI_LANGUAGE_FLAGS);

declare global {
  interface Window {
    googleTranslateElementInit?: () => void;
    google?: { translate?: { TranslateElement: (new (options: Record<string, unknown>, elementId: string) => unknown) & { InlineLayout: Record<string, unknown> } } };
  }
}

let scriptLoaded = false;

function currentGoogTransLanguage(): string {
  const match = document.cookie.match(/googtrans=\/en\/([a-zA-Z-]+)/);
  return match?.[1] ?? "en";
}

export default function GoogleTranslate() {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("en");
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCurrent(currentGoogTransLanguage());

    window.googleTranslateElementInit = () => {
      if (!window.google?.translate) return;
      new window.google.translate.TranslateElement(
        {
          pageLanguage: "en",
          includedLanguages: SUPPORTED_LANGUAGES.join(","),
          autoDisplay: false,
          layout: window.google.translate.TranslateElement.InlineLayout.SIMPLE,
        },
        "google_translate_element"
      );
    };

    if (!scriptLoaded) {
      const script = document.createElement("script");
      script.src = "https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
      script.async = true;
      document.body.appendChild(script);
      scriptLoaded = true;
    } else {
      window.googleTranslateElementInit();
    }
  }, []);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function selectLanguage(lang: string) {
    // A 'change' event on Google's own hidden <select> only reliably
    // re-translates from the ORIGINAL (English) DOM -- found directly by
    // testing: switching from Portuguese straight to French left the
    // page showing Portuguese text while this button's own flag updated
    // to French. Setting the real `googtrans` cookie Google's widget
    // itself reads, then reloading, is what the widget actually needs
    // to re-translate reliably between two non-English languages.
    const domain = window.location.hostname;
    if (lang === "en") {
      document.cookie = `googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=${domain}`;
      document.cookie = "googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
    } else {
      document.cookie = `googtrans=/en/${lang}; path=/; domain=${domain}`;
      document.cookie = `googtrans=/en/${lang}; path=/`;
    }
    window.location.reload();
  }

  const activeFlag = UI_LANGUAGE_FLAGS[current];

  return (
    <div ref={containerRef} className="relative inline-block">
      {/* Google's real widget -- kept in the DOM (needed for
          translation to function) but hidden via .google-translate-widget
          in globals.css; never rendered visibly. */}
      <div id="google_translate_element" className="google-translate-widget" />

      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Language: ${activeFlag?.name ?? "English"}`}
        className="flex items-center gap-1 rounded-lg border border-border bg-surface px-2 py-1.5 hover:border-accent"
      >
        {activeFlag ? <Flag country={activeFlag.country} label={activeFlag.name} size={22} /> : <span className="text-xs text-foreground-muted">EN</span>}
        <span aria-hidden="true" className="text-xs text-foreground-muted">▾</span>
      </button>

      {open && (
        <div role="listbox" className="absolute right-0 z-30 mt-1 flex gap-1 rounded-xl border border-border bg-surface p-1.5 shadow-md">
          <button type="button" role="option" aria-selected={current === "en"} onClick={() => selectLanguage("en")} className={`rounded-lg p-1 ${current === "en" ? "ring-2 ring-accent" : "hover:bg-surface-muted"}`}>
            <Flag country="US" label="English" size={22} />
          </button>
          {SUPPORTED_LANGUAGES.filter((lang) => lang !== "en").map((lang) => {
            const flag = UI_LANGUAGE_FLAGS[lang];
            if (!flag) return null;
            return (
              <button
                key={lang}
                type="button"
                role="option"
                aria-selected={lang === current}
                onClick={() => selectLanguage(lang)}
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
