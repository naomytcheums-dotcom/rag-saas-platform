"use client";

import Image from "next/image";

const TABS = [
  { icon: "blocks", title: "Choose your sections", desc: "Choose among 100+ components to build a landing page suited to the needs of your product.", active: true },
  { icon: "square-pen", title: "Add your content", desc: "Fill the blanks with screenshots, videos, and other content featuring your product.", active: false },
  { icon: "palette", title: "Customize", desc: "Make design yours in no time by changing the variables that control colors, typography, and other styles.", active: false },
];

export default function LandingTabs() {
  return (
    <div className="relative isolate mx-auto flex w-full max-w-[1312px] flex-col items-center gap-24 bg-white px-8 py-20">
      <div className="z-[2] flex w-full flex-col items-center gap-8 text-center">
        <p
          className="w-[1248px] max-w-full bg-clip-text text-5xl font-semibold leading-none text-transparent"
          style={{ backgroundImage: "linear-gradient(146deg, rgb(9,9,11) 24.451%, rgb(113,113,122) 73.781%)" }}
        >
          Make the right impression
        </p>
        <p className="w-[578px] max-w-full text-xl font-medium leading-7 text-[#71717a]">
          Launch UI makes it easy to build an unforgetable website that resonates with professional design-centric
          audiences.
        </p>
      </div>
      <div className="z-[1] flex w-full flex-wrap items-start justify-center gap-4">
        <div className="flex w-[373px] min-w-[240px] flex-col gap-3">
          {TABS.map((tab) => (
            <div
              key={tab.title}
              className={
                tab.active
                  ? "flex w-full items-start gap-2 rounded-md border border-[rgba(9,9,11,0.2)] bg-gradient-to-t from-[rgba(9,9,11,0.05)] to-[rgba(9,9,11,0.1)] py-3 pl-3 pr-5"
                  : "flex w-full items-start gap-2 rounded-md py-3 pl-3 pr-5"
              }
            >
              <div className="flex shrink-0 items-center p-0.5">
                <Image src={`/landing/icons/${tab.icon}.svg`} alt="" width={16} height={16} className="size-4" />
              </div>
              <div className={`flex flex-1 flex-col ${tab.active ? "" : "text-[#71717a]"}`}>
                <p className={`text-sm font-semibold leading-5 ${tab.active ? "text-[#09090b]" : ""}`}>{tab.title}</p>
                <p className="text-xs font-medium leading-4">{tab.desc}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="aspect-[859/482] min-w-[240px] flex-1 overflow-hidden rounded-xl border border-[rgba(9,9,11,0.1)] bg-white p-8">
          <div className="relative h-[850px] w-full rounded-xl">
            <div className="pointer-events-none absolute -left-[217px] -right-[248px] -top-[285px] h-[1069px]">
              <Image src="/landing/illustrations/glows.svg" alt="" fill />
            </div>
            <div className="absolute inset-x-0 top-0 flex flex-col items-start rounded-2xl bg-[rgba(9,9,11,0.05)] px-2 pt-2">
              <div className="relative aspect-[1232/753] w-full rounded-lg border border-white">
                <div className="absolute inset-0 overflow-hidden rounded-lg">
                  <Image src="/landing/illustrations/tabs-screenshot.png" alt="" fill className="object-cover" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
