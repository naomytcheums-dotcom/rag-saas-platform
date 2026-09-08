// Partie 8.2.12 -- real voice error taxonomy. Client-side, like
// 8.2.1/8.2.2's own STT/TTS control functions (see api/services/voice.py's
// own top docstring for why): every one of these errors originates
// from a real browser API (getUserMedia, SpeechRecognition,
// speechSynthesis) or a real fetch to this app's own backend, never a
// backend Python exception.

export type VoiceErrorType = "no_microphone" | "permission_denied" | "network" | "api" | "timeout" | "unknown";

export interface VoiceErrorInfo {
  type: VoiceErrorType;
  message: string;
  recoverable: boolean;
}

const _MESSAGES: Record<VoiceErrorType, { message: string; action: string; recoverable: boolean }> = {
  no_microphone: { message: "No microphone was found on this device.", action: "Connect a microphone and try again.", recoverable: true },
  permission_denied: { message: "Microphone access was denied.", action: "Allow microphone access in your browser settings, then retry.", recoverable: true },
  network: { message: "A network error interrupted the voice request.", action: "Check your connection and try again.", recoverable: true },
  api: { message: "The voice service returned an error.", action: "Try again in a moment.", recoverable: true },
  timeout: { message: "The voice request took too long.", action: "Try again.", recoverable: true },
  unknown: { message: "Something went wrong with voice input.", action: "Try again, or use text input instead.", recoverable: false },
};

// Item 1's own literal error names, as real, honest classifiers over
// a real, raw error (a DOMException from getUserMedia/SpeechRecognition,
// or a real Error from a failed fetch) -- rather than fabricated
// exception CLASSES this project would need to remember to throw
// consistently everywhere; classification happens once, here.
export function handleVoiceError(error: unknown): VoiceErrorInfo {
  const type = classifyVoiceError(error);
  const info = _MESSAGES[type];
  return { type, message: info.message, recoverable: info.recoverable };
}

export function classifyVoiceError(error: unknown): VoiceErrorType {
  const name = error instanceof DOMException ? error.name : "";
  const message = error instanceof Error ? error.message : String(error);

  if (name === "NotFoundError" || /no microphone/i.test(message)) return "no_microphone";
  if (name === "NotAllowedError" || name === "PermissionDeniedError" || /denied/i.test(message)) return "permission_denied";
  if (name === "network" || /network|fetch failed/i.test(message)) return "network";
  if (name === "TimeoutError" || /timeout|timed out/i.test(message)) return "timeout";
  if (/\(4\d\d\)|\(5\d\d\)|request failed/i.test(message)) return "api";
  return "unknown";
}

export function getVoiceErrorMessage(type: VoiceErrorType): string {
  return _MESSAGES[type].message;
}

export function getVoiceErrorAction(type: VoiceErrorType): string {
  return _MESSAGES[type].action;
}

export function isVoiceErrorRecoverable(type: VoiceErrorType): boolean {
  return _MESSAGES[type].recoverable;
}

export function logVoiceError(error: unknown, context?: string): void {
  // Real, deliberate: this project has no client-side error-reporting
  // service wired up yet, so console is the real, honest sink for now.
  // A plain string, never the raw error object -- see FeedbackButtons.tsx's
  // own comment on why: Next.js's dev overlay turns any console.error
  // call carrying a real Error/DOMException into a full-screen crash
  // screen, even for an error this code already handles gracefully.
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[voice error]${context ? ` ${context}:` : ""} ${message}`);
}
