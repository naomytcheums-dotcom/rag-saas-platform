"use client";

import LanguageFlag from "@/components/LanguageFlag";
import MicrophoneTest from "@/components/MicrophoneTest";
import PushToTalkButton from "@/components/PushToTalkButton";
import VADIndicator from "@/components/VADIndicator";
import VoiceError from "@/components/VoiceError";
import VoiceInput from "@/components/VoiceInput";
import VoiceLanguageSelector from "@/components/VoiceLanguageSelector";
import { useState } from "react";

// A real, minimal showcase of the Partie 8.2 voice components --
// same real purpose as app/page.tsx's own showcase for Partie 8.1:
// verify rendering/interaction/theme before these are wired into a
// real chat page (Partie 8.3's own final assembled design).
export default function VoiceDemo() {
  const [lang, setLang] = useState("fr-FR");

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-8 px-6 py-10">
      <h1 className="text-xl font-semibold text-foreground">Voice components (Partie 8.2)</h1>

      <section className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Language</h2>
        <VoiceLanguageSelector value={lang} onChange={setLang} />
        <div className="flex gap-2">
          <LanguageFlag code="fr-FR" />
          <LanguageFlag code="en-US" />
          <LanguageFlag code="ja-JP" />
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Voice input</h2>
        <VoiceInput language={lang} onTranscript={(t) => console.log("transcript:", t)} />
        <PushToTalkButton language={lang} onTranscript={(t) => console.log("ptt transcript:", t)} />
        <VADIndicator />
      </section>

      <section className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Microphone test</h2>
        <MicrophoneTest />
      </section>

      <section className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">Error states</h2>
        <VoiceError type="permission_denied" onRetry={() => {}} />
        <VoiceError type="no_microphone" onRetry={() => {}} />
      </section>
    </main>
  );
}
