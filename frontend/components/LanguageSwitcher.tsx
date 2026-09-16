"use client";

import "next-google-translate-widget/styles";
import GoogleTranslate, { LANGUAGES } from "next-google-translate-widget";

// Replaces the hand-rolled components/GoogleTranslate.tsx (Google's raw
// translate widget driven by a custom flags dropdown) -- that component
// had a real, reported bug: React would throw removeChild errors after
// a translate/reload cycle because Google's script mutates DOM nodes
// React still thinks it owns. next-google-translate-widget owns its own
// isolated container instead of touching this app's own React tree, so
// there's nothing left for React to lose track of.
const LANGS = LANGUAGES.filter((l) => ["en", "fr", "es", "de", "pt"].includes(l.value));

export default function LanguageSwitcher() {
  return <GoogleTranslate pageLanguage="fr" languages={LANGS} menuAlign="right" className="app-translate" />;
}
