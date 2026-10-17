"use client";

import { useEffect, useRef, useState } from "react";
import { synthesizeSpeech } from "@/lib/voiceApi";
import { getSpeechSynthesis } from "@/lib/speechTypes";
import { settings } from "@/lib/voiceConfig";
import { chunkTextForVoice } from "@/lib/voiceQueue";
import { classifyVoiceError, logVoiceError, type VoiceErrorType } from "@/lib/voiceErrors";
import VoiceError from "./VoiceError";

interface VoiceOutputProps {
  text: string;
  streaming?: boolean;
  provider?: "web_speech" | "elevenlabs" | "google_cloud" | "local";
  voiceId?: string;
}

type PlaybackState = "idle" | "speaking" | "paused";

// Partie 8.2.2 (Text-to-speech) + 8.2.3 (Streaming voice). web_speech playback
// (free, no key) goes through speechSynthesis, sentence by sentence when
// `streaming` is set (highlight + progress, see lib/voiceQueue.ts). The hosted
// providers (ElevenLabs / Google Cloud) go through this app's /voice/tts
// endpoint; when `streaming` is set the text is cut into the same sentence
// chunks, each chunk is synthesized separately and the NEXT chunk is already
// being synthesized while the current one plays, so the first words are heard
// after one short synthesis instead of after the whole answer, and playback
// has no gap between sentences.
export default function VoiceOutput({ text, streaming = false, provider = "web_speech", voiceId }: VoiceOutputProps) {
  const [state, setState] = useState<PlaybackState>("idle");
  const [chunkIndex, setChunkIndex] = useState(0);
  const [error, setError] = useState<VoiceErrorType | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playbackId = useRef(0); // bumped by stop()/play(): a hosted playback loop that sees another id ends silently

  const chunks = streaming ? chunkTextForVoice(text, settings.STREAMING_VOICE_CHUNK_SIZE) : [text];

  useEffect(() => () => {
    playbackId.current++;
    audioRef.current?.pause();
    getSpeechSynthesis()?.cancel();
  }, []);

  function speakChunk(index: number) {
    const synth = getSpeechSynthesis();
    if (!synth || index >= chunks.length) {
      setState("idle");
      return;
    }
    const utterance = new SpeechSynthesisUtterance(chunks[index]);
    utterance.rate = settings.TTS_SPEED;
    utterance.pitch = settings.TTS_PITCH;
    utterance.volume = settings.TTS_VOLUME;
    utterance.onend = () => {
      setChunkIndex(index + 1);
      speakChunk(index + 1);
    };
    utterance.onerror = (event) => {
      logVoiceError(event, "VoiceOutput");
      setError(classifyVoiceError(new Error(event.error)));
      setState("idle");
    };
    synth.speak(utterance);
  }

  function playBlob(blob: Blob): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      const done = () => URL.revokeObjectURL(url);
      audio.onended = () => {
        done();
        resolve();
      };
      audio.onerror = () => {
        done();
        reject(new Error("audio playback failed"));
      };
      audio.play().catch((err) => {
        done();
        reject(err);
      });
    });
  }

  async function play() {
    setError(null);
    if (provider !== "web_speech") {
      if (chunks.length === 0) return;
      const id = ++playbackId.current;
      try {
        setState("speaking");
        setChunkIndex(0);
        let next: Promise<Blob> | null = synthesizeSpeech(chunks[0], voiceId, provider);
        for (let i = 0; i < chunks.length; i++) {
          const blob = await (next as Promise<Blob>);
          if (playbackId.current !== id) return;
          next = i + 1 < chunks.length ? synthesizeSpeech(chunks[i + 1], voiceId, provider) : null; // prefetch the next sentence while this one plays
          next?.catch(() => undefined); // a failure is reported when that chunk's turn comes, not as an unhandled rejection now
          setChunkIndex(i);
          await playBlob(blob);
          if (playbackId.current !== id) return;
        }
        setState("idle");
      } catch (err) {
        if (playbackId.current !== id) return;
        logVoiceError(err, "VoiceOutput");
        setError(classifyVoiceError(err));
        setState("idle");
      }
      return;
    }

    const synth = getSpeechSynthesis();
    if (!synth) {
      setError("unknown");
      return;
    }
    setChunkIndex(0);
    setState("speaking");
    speakChunk(0);
  }

  function pause() {
    if (provider === "web_speech") getSpeechSynthesis()?.pause();
    else audioRef.current?.pause();
    setState("paused");
  }

  function resume() {
    if (provider === "web_speech") getSpeechSynthesis()?.resume();
    else void audioRef.current?.play();
    setState("speaking");
  }

  function stop() {
    playbackId.current++; // ends a hosted playback loop at its next step
    if (provider === "web_speech") getSpeechSynthesis()?.cancel();
    else audioRef.current?.pause();
    setState("idle");
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1">
        {state === "idle" && (
          <button type="button" onClick={() => void play()} aria-label="Play" className="rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent-soft hover:text-accent-hover">
            ▶ Play
          </button>
        )}
        {state === "speaking" && (
          <button type="button" onClick={pause} aria-label="Pause" className="rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent-soft hover:text-accent-hover">
            ⏸ Pause
          </button>
        )}
        {state === "paused" && (
          <button type="button" onClick={resume} aria-label="Resume" className="rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent-soft hover:text-accent-hover">
            ▶ Resume
          </button>
        )}
        {state !== "idle" && (
          <button type="button" onClick={stop} aria-label="Stop" className="rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-danger-soft hover:text-danger">
            ⏹ Stop
          </button>
        )}
      </div>

      {streaming && state !== "idle" && chunks.length > 1 && (
        <p className="text-xs text-foreground-muted">
          {Math.min(chunkIndex + 1, chunks.length)} / {chunks.length} phrases
        </p>
      )}

      {error && <VoiceError type={error} onRetry={play} />}
    </div>
  );
}
