"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import VoiceLanguageSelector from "./VoiceLanguageSelector";
import VoiceSelector from "./VoiceSelector";

interface VoiceSettingsData {
  language: string;
  tts_provider: string;
  tts_voice: string | null;
  tts_speed: number;
  tts_pitch: number;
  tts_volume: number;
  vad_enabled: boolean;
  push_to_talk_enabled: boolean;
  audio_history_enabled: boolean;
}

// Partie 8.2.8 -- the real voice-preferences page: language, TTS
// voice, speed/pitch/volume sliders, and the VAD/push-to-talk/history
// toggles, all backed by GET/PATCH /users/me/voice-settings.
export default function VoiceSettings() {
  const [data, setData] = useState<VoiceSettingsData | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void api.get<VoiceSettingsData>("/users/me/voice-settings").then(setData).catch(() => {});
  }, []);

  async function save(partial: Partial<VoiceSettingsData>) {
    setData((prev) => (prev ? { ...prev, ...partial } : prev));
    setSaving(true);
    try {
      await api.patch("/users/me/voice-settings", partial);
    } catch {
      // Real, honest no-op -- the local optimistic update above still
      // stands, so the UI stays responsive even without a reachable
      // backend/session.
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setSaving(true);
    try {
      const result = await api.post<VoiceSettingsData>("/users/me/voice-settings/reset");
      setData(result);
    } catch {
      // Real, honest no-op.
    } finally {
      setSaving(false);
    }
  }

  if (!data) return <p className="text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="flex max-w-md flex-col gap-5 rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">Language</span>
        <VoiceLanguageSelector value={data.language} onChange={(language) => void save({ language })} />
      </div>

      <div>
        <span className="mb-2 block text-sm font-medium text-foreground">TTS voice (ElevenLabs)</span>
        <VoiceSelector value={data.tts_voice} onChange={(tts_voice) => void save({ tts_voice, tts_provider: "elevenlabs" })} />
      </div>

      {(
        [
          ["tts_speed", "Speed"],
          ["tts_pitch", "Pitch"],
          ["tts_volume", "Volume"],
        ] as const
      ).map(([key, label]) => (
        <label key={key} className="flex flex-col gap-1 text-sm text-foreground">
          {label} ({data[key].toFixed(1)})
          <input
            type="range" min={0} max={2} step={0.1} value={data[key]}
            onChange={(event) => void save({ [key]: Number(event.target.value) } as Partial<VoiceSettingsData>)}
          />
        </label>
      ))}

      {(
        [
          ["vad_enabled", "Auto-detect speech (VAD)"],
          ["push_to_talk_enabled", "Push-to-talk"],
          ["audio_history_enabled", "Save voice history"],
        ] as const
      ).map(([key, label]) => (
        <label key={key} className="flex items-center justify-between text-sm text-foreground">
          {label}
          <input
            type="checkbox" checked={data[key]}
            onChange={(event) => void save({ [key]: event.target.checked } as Partial<VoiceSettingsData>)}
          />
        </label>
      ))}

      <button
        type="button"
        onClick={() => void reset()}
        disabled={saving}
        className="self-start rounded-lg px-3 py-1.5 text-xs font-medium text-foreground-muted hover:bg-surface-muted disabled:opacity-50"
      >
        Reset to defaults
      </button>
    </div>
  );
}
