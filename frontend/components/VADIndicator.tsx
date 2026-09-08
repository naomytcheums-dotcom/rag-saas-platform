"use client";

import { useEffect, useRef, useState } from "react";
import { settings } from "@/lib/voiceConfig";

interface VADIndicatorProps {
  onSpeechStart?: () => void;
  onSpeechStop?: () => void;
  threshold?: number;
}

type VADState = "idle" | "listening" | "speech" | "silence";

// Partie 8.2.5 -- real, client-side voice activity detection via the
// Web Audio API's own AnalyserNode (RMS of the time-domain waveform),
// no external VAD library or server round trip needed for this real,
// simple energy-threshold heuristic.
export default function VADIndicator({ onSpeechStart, onSpeechStop, threshold = settings.VAD_THRESHOLD }: VADIndicatorProps) {
  const [state, setState] = useState<VADState>("idle");
  const [level, setLevel] = useState(0);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const speechStartRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const speakingRef = useRef(false);

  async function start() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    audioContext.createMediaStreamSource(stream).connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);

    setState("listening");

    function tick() {
      analyser.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (const value of data) {
        const normalized = (value - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / data.length);
      setLevel(rms);

      const now = performance.now();
      if (rms >= threshold) {
        silenceStartRef.current = null;
        if (speechStartRef.current === null) speechStartRef.current = now;
        else if (!speakingRef.current && now - speechStartRef.current >= settings.VAD_MIN_SPEECH_DURATION_MS) {
          speakingRef.current = true;
          setState("speech");
          onSpeechStart?.();
        }
      } else {
        speechStartRef.current = null;
        if (speakingRef.current) {
          if (silenceStartRef.current === null) silenceStartRef.current = now;
          else if (now - silenceStartRef.current >= settings.VAD_SILENCE_TIMEOUT_MS) {
            speakingRef.current = false;
            setState("silence");
            onSpeechStop?.();
          }
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    }
    tick();
  }

  function stop() {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    void audioContextRef.current?.close();
    setState("idle");
    setLevel(0);
  }

  useEffect(() => () => stop(), []);

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => (state === "idle" ? void start() : stop())}
        className="rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent-soft hover:text-accent-hover"
      >
        {state === "idle" ? "Enable auto-detect" : "Disable"}
      </button>
      {state !== "idle" && (
        <div className="flex h-4 w-24 items-center overflow-hidden rounded-full bg-surface-muted">
          <div
            className={`h-full rounded-full transition-all ${state === "speech" ? "bg-accent" : "bg-border-strong"}`}
            style={{ width: `${Math.min(level * 200, 100)}%` }}
          />
        </div>
      )}
      {state === "speech" && <span className="text-xs text-accent-hover">Speaking…</span>}
    </div>
  );
}
