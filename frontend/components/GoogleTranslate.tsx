"use client";

import { useEffect } from "react";
import { UI_LANGUAGE_FLAGS } from "@/lib/voiceConfig";

// Replaces the old per-string i18n dictionary (lib/i18n.tsx) as the
// site-wide translator, per direct user feedback: the dictionary only
// covered components that explicitly called useTranslation(), so most
// pages never visibly changed language. Google's website-translate
// widget translates the whole rendered DOM instead, so every page
// benefits immediately, no per-string wiring needed.
const SUPPORTED_LANGUAGES = Object.keys(UI_LANGUAGE_FLAGS);

declare global {
  interface Window {
    googleTranslateElementInit?: () => void;
    google?: { translate?: { TranslateElement: new (options: Record<string, unknown>, elementId: string) => unknown } };
  }
}

let scriptLoaded = false;

export default function GoogleTranslate() {
  useEffect(() => {
    window.googleTranslateElementInit = () => {
      if (!window.google?.translate) return;
      new window.google.translate.TranslateElement(
        {
          pageLanguage: "en",
          includedLanguages: SUPPORTED_LANGUAGES.join(","),
          autoDisplay: false,
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

  return <div id="google_translate_element" className="google-translate-widget" />;
}
