// Test harness: mounts the REAL VADIndicator and VoiceOutput components (frontend/components) in a bare page so a real Chromium, with a fake microphone
// that plays a WAV file, can drive them. Nothing here re-implements their logic. See tests/contracts/test_browser_voice.py.
import { createRoot } from "react-dom/client";
import VADIndicator from "@/components/VADIndicator";
import VoiceOutput from "@/components/VoiceOutput";

declare global {
  interface Window {
    __voice: { events: { event: string; t: number }[]; levels: number[]; audioPlays: { t: number; duration: number }[] };
  }
}

const started = performance.now();
window.__voice = { events: [], levels: [], audioPlays: [] };
const mark = (event: string) => window.__voice.events.push({ event, t: Math.round(performance.now() - started) });

// Record every <audio> the output component plays (it creates them with `new Audio()`), with when they start and end.
const NativeAudio = window.Audio;
window.Audio = function (this: unknown, src?: string) {
  const audio = new NativeAudio(src);
  audio.addEventListener("playing", () => mark(`audio-playing:${Math.round(audio.duration * 1000)}ms`));
  audio.addEventListener("ended", () => mark("audio-ended"));
  return audio;
} as unknown as typeof Audio;

const params = new URLSearchParams(location.search);
const threshold = params.get("threshold");

createRoot(document.getElementById("root")!).render(
  <div>
    <section id="vad">
      <VADIndicator onSpeechStart={() => mark("speech-start")} onSpeechStop={() => mark("speech-stop")} {...(threshold ? { threshold: Number(threshold) } : {})} />
    </section>
    <section id="output">
      <VoiceOutput
        text={params.get("text") ?? "The invoice is due on the fifteenth. Please pay by Friday. Thank you."}
        streaming
        provider={(params.get("provider") as "elevenlabs" | "google_cloud" | null) ?? "elevenlabs"}
      />
    </section>
  </div>,
);
