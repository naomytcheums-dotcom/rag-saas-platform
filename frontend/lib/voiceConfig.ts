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

export const VOICE_LANGUAGES = [
  { code: "fr-FR", name: "Français", flag: "🇫🇷" },
  { code: "en-US", name: "English", flag: "🇺🇸" },
  { code: "es-ES", name: "Español", flag: "🇪🇸" },
  { code: "de-DE", name: "Deutsch", flag: "🇩🇪" },
  { code: "pt-PT", name: "Português", flag: "🇵🇹" },
  { code: "ar-SA", name: "العربية", flag: "🇸🇦" },
  { code: "it-IT", name: "Italiano", flag: "🇮🇹" },
  { code: "nl-NL", name: "Nederlands", flag: "🇳🇱" },
  { code: "pl-PL", name: "Polski", flag: "🇵🇱" },
  { code: "ru-RU", name: "Русский", flag: "🇷🇺" },
  { code: "zh-CN", name: "中文", flag: "🇨🇳" },
  { code: "ja-JP", name: "日本語", flag: "🇯🇵" },
] as const;

export type VoiceLanguage = (typeof VOICE_LANGUAGES)[number];
