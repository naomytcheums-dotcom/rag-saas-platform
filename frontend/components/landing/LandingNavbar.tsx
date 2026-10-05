"use client";

import Image from "next/image";

export default function LandingNavbar() {
  return (
    <div className="relative mx-auto flex w-full max-w-[1312px] items-center justify-between px-8 py-4">
      <div className="flex items-center gap-4">
        <div className="flex w-[116px] items-center gap-2">
          <div className="relative size-6 rounded">
            <Image src="/landing/icons/favicon.svg" alt="" fill />
          </div>
          <p className="text-lg font-bold leading-7 text-[#09090b]">Launch UI</p>
        </div>
        <button type="button" className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-[#09090b]">
          Getting started
          <Image src="/landing/icons/chevron-down.svg" alt="" width={12} height={12} className="size-3" />
        </button>
        <button type="button" className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-[#09090b]">
          Components
          <Image src="/landing/icons/chevron-down.svg" alt="" width={12} height={12} className="size-3" />
        </button>
        <button type="button" className="rounded-md px-4 py-2 text-sm font-medium text-[#09090b]">
          Documentation
        </button>
      </div>

      <div className="flex items-start gap-4">
        <button type="button" className="rounded-md px-4 py-2 text-sm font-medium text-[#09090b]">
          Sign in
        </button>
        <a
          href="https://www.mikolajdobrucki.com/jupiter?ref=figma"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 rounded-md bg-gradient-to-b from-[#18181b] to-[rgba(9,9,11,0.8)] px-4 py-2 text-sm font-medium text-[#fafafa] shadow-[0px_1px_2px_0px_rgba(0,0,0,0.1),0px_1px_3px_0px_rgba(0,0,0,0.1)]"
        >
          Get started
        </a>
      </div>
    </div>
  );
}
