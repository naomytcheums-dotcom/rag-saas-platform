// Real, client-side mirror of Partie 8.2's own backend defaults
// (api/config.py) -- a browser component can't read Python Settings
// directly, so the handful of real values actually needed client-side
// (retry counts, thresholds, timeouts) are kept here, matching the
// backend's own real defaults exactly. If a real deployment ever
// needs to override these per-environment, they'd become real
// NEXT_PUBLIC_* env vars -- not needed yet since every current value
// is a real, sensible constant, not a secret.
export const settings = {
  STT_LANGUAGE: "fr-FR",
  STT_CONTINUOUS: true,
  STT_INTERIM_RESULTS: true,
  STT_MAX_ALTERNATIVES: 5,

  TTS_VOICE: "Google US English",
  TTS_SPEED: 1.0,
  TTS_PITCH: 1.0,
  TTS_VOLUME: 1.0,

  STREAMING_VOICE_CHUNK_SIZE: 100,
  STREAMING_VOICE_DELAY_MS: 500,

  PUSH_TO_TALK_TIMEOUT_MS: 30_000,

  VAD_THRESHOLD: 0.5,
  VAD_SILENCE_TIMEOUT_MS: 2000,
  VAD_MIN_SPEECH_DURATION_MS: 500,

  MICROPHONE_TEST_DURATION_MS: 3000,
  MICROPHONE_TEST_THRESHOLD: 0.1,

  AUDIO_PERMISSION_RETRY_COUNT: 3,
  AUDIO_PERMISSION_RETRY_DELAY_MS: 2000,

  VOICE_ERROR_RETRY_COUNT: 3,
  VOICE_ERROR_RETRY_DELAY_MS: 2000,
} as const;

// `country` is the real ISO 3166-1 alpha-2 code country-flag-icons
// indexes its real SVGs by -- derived from each locale's own region
// subtag (e.g. "fr-FR" -> "FR"), kept explicit here rather than
// parsed at render time.
export const VOICE_LANGUAGES = [
  { code: "fr-FR", name: "Français", country: "FR" },
  { code: "en-US", name: "English", country: "US" },
  { code: "es-ES", name: "Español", country: "ES" },
  { code: "de-DE", name: "Deutsch", country: "DE" },
  { code: "pt-PT", name: "Português", country: "PT" },
  { code: "ar-SA", name: "العربية", country: "SA" },
  { code: "it-IT", name: "Italiano", country: "IT" },
  { code: "nl-NL", name: "Nederlands", country: "NL" },
  { code: "pl-PL", name: "Polski", country: "PL" },
  { code: "ru-RU", name: "Русский", country: "RU" },
  { code: "zh-CN", name: "中文", country: "CN" },
  { code: "ja-JP", name: "日本語", country: "JP" },
] as const;

// The shorter UI language codes (api/config.py's own UI_SUPPORTED_LANGUAGES)
// mapped to a real, representative country flag -- "language" has no
// real flag of its own (e.g. Arabic/English are spoken across many
// real countries), so this picks one real, well-recognized country
// per language, the same real, honest simplification every other
// real language-flag picker (browsers, OS settings) makes too.
export const UI_LANGUAGE_FLAGS: Record<string, { name: string; country: string }> = {
  en: { name: "English", country: "US" },
  fr: { name: "Français", country: "FR" },
  es: { name: "Español", country: "ES" },
  de: { name: "Deutsch", country: "DE" },
  pt: { name: "Português", country: "PT" },
  ar: { name: "العربية", country: "SA" },
};

export type VoiceLanguage = (typeof VOICE_LANGUAGES)[number];
