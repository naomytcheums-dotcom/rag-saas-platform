"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface VoiceSource {
  citation_number: number;
  document_name: string | null;
  source_title: string | null;
  source_url: string | null;
}

interface VoiceTurn {
  transcript: string;
  answer_text: string;
  answer_audio_base64: string | null;
  response_id: string;
  sources: VoiceSource[];
  credits_charged: number;
}

type Phase = "idle" | "recording" | "processing";

export default function VoiceAgentPage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const { t } = useTranslation();
  const [phase, setPhase] = useState<Phase>("idle");
  const [turn, setTurn] = useState<VoiceTurn | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState("local_whisper");
  const [speakServer, setSpeakServer] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stream = useRef<MediaStream | null>(null);

  useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), []);

  async function send(blob: Blob) {
    if (!org) return;
    setPhase("processing");
    try {
      const query = new URLSearchParams({ stt_provider: provider, speak: String(speakServer) });
      const result = await api.postMultipart<VoiceTurn>(
        `/voice/organizations/${org.id}/agent?${query.toString()}`,
        {},
        { file: new File([blob], "question.webm", { type: blob.type || "audio/webm" }) },
      );
      setTurn(result);
      if (result.answer_audio_base64) {
        void new Audio(`data:audio/mpeg;base64,${result.answer_audio_base64}`).play();
      } else if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.speak(new SpeechSynthesisUtterance(result.answer_text.replace(/\[\d+\]/g, "")));
      }
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("voice_agent.error_generic"));
    } finally {
      setPhase("idle");
    }
  }

  async function start() {
    setError(null);
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError(t("voice_agent.error_mic"));
      return;
    }
    chunks.current = [];
    const media = new MediaRecorder(stream.current);
    media.ondataavailable = (event) => chunks.current.push(event.data);
    media.onstop = () => {
      stream.current?.getTracks().forEach((track) => track.stop());
      void send(new Blob(chunks.current, { type: media.mimeType }));
    };
    recorder.current = media;
    media.start();
    setPhase("recording");
  }

  function stop() {
    recorder.current?.stop();
  }

  if (orgLoading) return <p>{t("voice_agent.loading")}</p>;

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">{t("voice_agent.title")}</h1>
        <p className="text-sm text-gray-600">{t("voice_agent.intro")}</p>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <label className="text-sm">
          {t("voice_agent.provider")}{" "}
          <select value={provider} onChange={(e) => setProvider(e.target.value)} className="border rounded px-2 py-1" disabled={phase !== "idle"}>
            <option value="local_whisper">Whisper (open source)</option>
            <option value="whisper">Whisper (OpenAI)</option>
            <option value="deepgram">Deepgram</option>
          </select>
        </label>
        <label className="text-sm flex items-center gap-2">
          <input type="checkbox" checked={speakServer} onChange={(e) => setSpeakServer(e.target.checked)} disabled={phase !== "idle"} />
          {t("voice_agent.speak_server")}
        </label>
      </div>

      <button
        type="button"
        onClick={phase === "recording" ? stop : start}
        disabled={phase === "processing" || !org}
        className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-50"
      >
        {phase === "recording" ? t("voice_agent.stop") : phase === "processing" ? t("voice_agent.processing") : t("voice_agent.start")}
      </button>

      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

      {turn && (
        <section className="space-y-3">
          <div>
            <h2 className="font-medium">{t("voice_agent.you_said")}</h2>
            <p className="text-sm">{turn.transcript}</p>
          </div>
          <div>
            <h2 className="font-medium">{t("voice_agent.answer")}</h2>
            <p className="text-sm whitespace-pre-wrap">{turn.answer_text}</p>
          </div>
          {turn.sources.length > 0 && (
            <div>
              <h2 className="font-medium">{t("voice_agent.sources")}</h2>
              <ul className="text-sm list-disc pl-5">
                {turn.sources.map((source) => (
                  <li key={source.citation_number}>
                    [{source.citation_number}] {source.source_title || source.document_name || t("voice_agent.unknown_source")}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
