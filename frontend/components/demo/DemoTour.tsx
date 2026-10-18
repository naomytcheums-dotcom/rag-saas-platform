"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "@/lib/i18n";

export interface DemoStep {
  id: string;
  title: string;
  caption: string;
  image: string;
  alt: string;
  /** Second of the video at which this step starts. */
  video_at: number;
}

export interface DemoManifest {
  recorded: string;
  video: { src: string; poster?: string; captions?: string };
  steps: DemoStep[];
}

/** The interactive demo: the real screencast of the product plus a step-by-step walk through the same recording (screenshots taken by
 *  scripts/demo/record_demo.mjs while it drove the running application). Everything shown comes from /demo/manifest.json, which that script
 *  writes: no sample is typed by hand, so the page cannot drift from what the product really did. */
export default function DemoTour({ manifestUrl = "/demo/manifest.json" }: { manifestUrl?: string }) {
  const { t } = useTranslation();
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [failed, setFailed] = useState(false);
  const [index, setIndex] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(manifestUrl)
      .then((response) => { if (!response.ok) throw new Error(String(response.status)); return response.json() as Promise<DemoManifest>; })
      .then((data) => { if (!cancelled && Array.isArray(data.steps) && data.steps.length > 0) setManifest(data); else if (!cancelled) setFailed(true); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [manifestUrl]);

  const total = manifest?.steps.length ?? 0;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (event.key === "ArrowRight") setIndex((current) => Math.min(current + 1, Math.max(total - 1, 0)));
      if (event.key === "ArrowLeft") setIndex((current) => Math.max(current - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [total]);

  if (failed) return <p role="alert" className="text-center text-[#ff9777]">{t("demo.error")}</p>;
  if (!manifest) return <p className="text-center text-[#d9d9d9]" aria-live="polite">{t("demo.loading")}</p>;

  const step = manifest.steps[index];
  const seek = (seconds: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = seconds;
    void video.play().catch(() => {});
  };

  return (
    <div className="flex flex-col gap-14">
      <section aria-labelledby="demo-video-title">
        <h2 id="demo-video-title" className="mb-4 text-[24px] font-bold text-white">{t("demo.video_title")}</h2>
        <video ref={videoRef} className="w-full rounded-[20px] border-[1.25px] border-[rgba(255,84,31,0.3)] bg-black" controls preload="metadata" playsInline poster={manifest.video.poster}>
          <source src={manifest.video.src} type="video/mp4" />
          {manifest.video.captions ? <track kind="captions" src={manifest.video.captions} srcLang="en" label="English" default /> : null}
          {t("demo.novideo")}
        </video>
      </section>

      <section aria-labelledby="demo-steps-title">
        <h2 id="demo-steps-title" className="mb-2 text-[24px] font-bold text-white">{t("demo.steps_title")}</h2>
        <p className="mb-6 text-[14px] text-[#a8a8a8]">{t("demo.keyboard")}</p>
        <div className="grid gap-8 lg:grid-cols-[260px_1fr]">
          <ol className="flex flex-row gap-2 overflow-x-auto lg:flex-col" aria-label={t("demo.steps_title")}>
            {manifest.steps.map((item, position) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => setIndex(position)}
                  aria-current={position === index ? "step" : undefined}
                  className={`w-full whitespace-nowrap rounded-[10px] border px-4 py-3 text-left text-[15px] transition-colors lg:whitespace-normal ${position === index ? "border-[#ff541f] bg-[rgba(255,84,31,0.15)] text-white" : "border-[rgba(255,255,255,0.15)] text-[#d9d9d9] hover:border-[rgba(255,255,255,0.4)]"}`}
                >
                  <span className="mr-2 text-[#ff9777]">{position + 1}.</span>{item.title}
                </button>
              </li>
            ))}
          </ol>
          <div aria-live="polite">
            {/* eslint-disable-next-line @next/next/no-img-element -- recorded screenshots served as static files */}
            <img src={step.image} alt={step.alt} className="w-full rounded-[16px] border border-[rgba(255,255,255,0.15)]" />
            <p className="mt-4 text-[13px] uppercase tracking-wide text-[#ff9777]">{t("demo.step_of", { current: index + 1, total })}</p>
            <h3 className="mt-1 text-[22px] font-bold text-white">{step.title}</h3>
            <p className="mt-2 text-[17px] leading-[26px] text-[#d9d9d9]">{step.caption}</p>
            <div className="mt-5 flex flex-wrap gap-3">
              <button type="button" onClick={() => setIndex((current) => Math.max(current - 1, 0))} disabled={index === 0} className="rounded-[10px] border border-[rgba(255,255,255,0.3)] px-5 py-2 text-white disabled:opacity-40">{t("demo.prev")}</button>
              <button type="button" onClick={() => setIndex((current) => Math.min(current + 1, total - 1))} disabled={index === total - 1} className="rounded-[10px] bg-[#ff541f] px-5 py-2 font-bold text-white disabled:opacity-40">{t("demo.next")}</button>
              <button type="button" onClick={() => seek(step.video_at)} className="rounded-[10px] border border-[rgba(255,255,255,0.3)] px-5 py-2 text-white">▶ {Math.floor(step.video_at / 60)}:{String(Math.floor(step.video_at % 60)).padStart(2, "0")}</button>
            </div>
          </div>
        </div>
      </section>

      <p className="text-[14px] leading-[22px] text-[#a8a8a8]">{t("demo.recorded_note", { date: manifest.recorded })}</p>
      <div className="text-center">
        <Link href="/register" className="inline-block rounded-[10px] bg-[#ff541f] px-[35px] py-[15px] text-[20px] font-bold text-white">{t("demo.cta")}</Link>
      </div>
    </div>
  );
}
