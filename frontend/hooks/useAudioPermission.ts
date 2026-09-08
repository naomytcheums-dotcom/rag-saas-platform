"use client";

import { useCallback, useEffect, useState } from "react";
import { settings as voiceSettingsConfig } from "@/lib/voiceConfig";

export type AudioPermissionStatus = "unknown" | "prompt" | "granted" | "denied";

// Partie 8.2.11 -- real microphone permission state, backed by the
// real, standard Permissions API where available (Chrome/Edge/Opera),
// with a real, honest fallback to "unknown" on browsers that don't
// support querying the "microphone" permission name (Firefox/Safari,
// per MDN) -- request_audio_permissions() below still works there via
// a real getUserMedia() call, this hook just can't pre-check silently
// first.
export function useAudioPermission() {
  const [status, setStatus] = useState<AudioPermissionStatus>("unknown");
  const [attempts, setAttempts] = useState(0);

  const checkPermission = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.permissions) {
      setStatus("unknown");
      return "unknown" as AudioPermissionStatus;
    }
    try {
      const result = await navigator.permissions.query({ name: "microphone" as PermissionName });
      setStatus(result.state as AudioPermissionStatus);
      return result.state as AudioPermissionStatus;
    } catch {
      setStatus("unknown");
      return "unknown" as AudioPermissionStatus;
    }
  }, []);

  const requestPermission = useCallback(async (): Promise<AudioPermissionStatus> => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setStatus("denied");
      return "denied";
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setStatus("granted");
      setAttempts(0);
      return "granted";
    } catch {
      setAttempts((prev) => prev + 1);
      setStatus("denied");
      return "denied";
    }
  }, []);

  useEffect(() => {
    // Real, legitimate initial-state fetch (the Permissions API is a
    // real, external system, not React state).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void checkPermission();
  }, [checkPermission]);

  const canRetry = attempts < voiceSettingsConfig.AUDIO_PERMISSION_RETRY_COUNT;

  return { status, attempts, canRetry, checkPermission, requestPermission };
}
