"use client";

import { useEffect, useRef, useState } from "react";
import { settings } from "@/lib/voiceConfig";
import { classifyVoiceError, type VoiceErrorType } from "@/lib/voiceErrors";
import VoiceError from "./VoiceError";

type TestState = "idle" | "testing" | "success" | "failed";

// Partie 8.2.10 -- real microphone test: records real input for
// MICROPHONE_TEST_DURATION, and passes only if the real peak level
// crosses MICROPHONE_TEST_THRESHOLD at least once (silence -> real,
// honest failure, not a false "it works").
export default function MicrophoneTest() {
  const [state, setState] = useState<TestState>("idle");
  const [level, setLevel] = useState(0);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [error, setError] = useState<VoiceErrorType | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    navigator.mediaDevices
      ?.enumerateDevices()
      .then((all) => setDevices(all.filter((d) => d.kind === "audioinput")))
      .catch(() => setDevices([]));
  }, []);

  async function runTest() {
    setError(null);
    setState("testing");
    let peak = 0;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      setError(classifyVoiceError(err));
      setState("failed");
      return;
    }

    const audioContext = new AudioContext();
    const analyser = audioContext.createAnalyser();
    audioContext.createMediaStreamSource(stream).connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    const startedAt = performance.now();

    function tick() {
      analyser.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (const value of data) {
        const normalized = (value - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / data.length);
      peak = Math.max(peak, rms);
      setLevel(rms);

      if (performance.now() - startedAt < settings.MICROPHONE_TEST_DURATION_MS) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        stream.getTracks().forEach((track) => track.stop());
        void audioContext.close();
        setState(peak >= settings.MICROPHONE_TEST_THRESHOLD ? "success" : "failed");
        if (peak < settings.MICROPHONE_TEST_THRESHOLD) setError("no_microphone");
      }
    }
    tick();
  }

  useEffect(() => () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  }, []);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <p className="text-sm text-foreground">
        {state === "idle" && "Test your microphone before using voice features."}
        {state === "testing" && "Speak now…"}
        {state === "success" && "Your microphone is working."}
        {state === "failed" && "We didn't detect any sound."}
      </p>

      <div className="h-3 w-full overflow-hidden rounded-full bg-surface-muted">
        <div
          className={`h-full rounded-full transition-all ${state === "success" ? "bg-success" : "bg-accent"}`}
          style={{ width: `${Math.min(level * 200, 100)}%` }}
        />
      </div>

      <button
        type="button"
        onClick={() => void runTest()}
        disabled={state === "testing"}
        className="self-start rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        {state === "testing" ? "Testing…" : "Start test"}
      </button>

      {devices.length > 0 && (
        <p className="text-xs text-foreground-muted">{devices.length} microphone(s) detected: {devices.map((d) => d.label || "Unnamed device").join(", ")}</p>
      )}

      {error && <VoiceError type={error} onRetry={runTest} />}
    </div>
  );
}
