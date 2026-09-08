// Thin helpers for Partie 8.2's own real, server-side voice endpoints
// (api/routers/voice.py) -- distinct from lib/api.ts's own generic
// JSON request() helper, since these send/receive real binary audio,
// not JSON.

import { fileUrl } from "@/lib/api";

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("access_token");
}

export async function synthesizeSpeech(text: string, voiceId?: string): Promise<Blob> {
  const token = getAccessToken();
  const response = await fetch(fileUrl("/voice/tts"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ text, voice_id: voiceId }),
  });
  if (!response.ok) throw new Error(`TTS request failed (${response.status})`);
  return response.blob();
}

export async function transcribeAudio(blob: Blob, provider?: string, language?: string): Promise<string> {
  const token = getAccessToken();
  const formData = new FormData();
  formData.append("file", blob, "recording.webm");
  const params = new URLSearchParams();
  if (provider) params.set("provider", provider);
  if (language) params.set("language", language);

  const response = await fetch(fileUrl(`/voice/stt?${params.toString()}`), {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });
  if (!response.ok) throw new Error(`STT request failed (${response.status})`);
  const data = (await response.json()) as { text: string };
  return data.text;
}
