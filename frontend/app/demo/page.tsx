"use client";

import SiteHeader from "@/components/figma/SiteHeader";
import DemoTour from "@/components/demo/DemoTour";
import { useTranslation } from "@/lib/i18n";

// Interactive demo (spec 14.2.7 / 14.3.2): the recorded screencast and a step-by-step walk through the same recording. The assets in
// public/demo/ are produced by scripts/demo/record_demo.mjs against the running product; see docs/commercial/DEMO.md.
export default function DemoPage() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-[#010101] text-white">
      <SiteHeader />
      <main className="mx-auto w-full max-w-[1100px] px-6 pb-24 pt-6">
        <h1 className="text-[40px] font-bold leading-[48px]">{t("demo.title")}</h1>
        <p className="mb-12 mt-4 max-w-[780px] text-[20px] leading-[28px] text-[#d9d9d9]">{t("demo.subtitle")}</p>
        <DemoTour />
      </main>
    </div>
  );
}
