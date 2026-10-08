import Image from "next/image";

export default function LandingBento() {
  return (
    <div className="mx-auto flex w-full max-w-[1312px] flex-col items-start gap-12 bg-white px-8 py-20">
      <p className="text-5xl font-semibold leading-none text-[#09090b]">Build a better website, faster.</p>
      <div className="flex w-full flex-col gap-4">
        <div className="flex h-[496px] w-full flex-wrap items-center gap-4">
          <div className="flex h-full w-[560px] min-w-[360px] flex-col gap-6 overflow-hidden rounded-xl border border-[rgba(9,9,11,0.2)] bg-white p-6">
            <div className="flex w-full max-w-[460px] flex-col gap-2">
              <p className="text-2xl font-semibold leading-8 text-[#09090b]">100+ sections and components</p>
              <p className="text-base font-normal leading-6 text-[#71717a]">
                All the elements you need to build a modern, responsive, and accessible landing page.
              </p>
            </div>
            <div className="relative min-h-px flex-1 pt-32">
              <Image src="/landing/illustrations/globe.svg" alt="" fill className="object-contain" />
            </div>
          </div>
          <div className="flex h-full min-w-[360px] flex-1 flex-col gap-6 overflow-hidden rounded-xl border border-[rgba(9,9,11,0.2)] bg-white p-6">
            <div className="flex w-full max-w-[460px] flex-col gap-2">
              <p className="text-2xl font-semibold leading-8 text-[#09090b]">You&apos;re in control</p>
              <p className="text-base font-normal leading-6 text-[#71717a]">
                This is not a component library. It&apos;s a collection of re-usable components that you can copy and
                paste into your apps.
              </p>
            </div>
            <div className="relative min-h-px flex-1 pt-16">
              <Image src="/landing/illustrations/ripple.svg" alt="" fill className="object-contain" />
            </div>
          </div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-4">
          <div className="flex h-[560px] min-w-[360px] flex-1 flex-col gap-6 overflow-hidden rounded-xl border border-[rgba(9,9,11,0.2)] bg-white p-6">
            <div className="flex w-full max-w-[460px] flex-col gap-2">
              <p className="text-2xl font-semibold leading-8 text-[#09090b]">Fits right into your stack</p>
              <div className="text-base font-normal leading-6 text-[#71717a]">
                <p className="mb-2">Built with modern web technologies and tools that fit right into any React project.</p>
                <p>No bloat, no extra dependencies, no risk of conflicts.</p>
              </div>
            </div>
            <div className="relative min-h-px flex-1">
              <Image src="/landing/illustrations/ripple.svg" alt="" fill className="object-contain" />
            </div>
          </div>
          <div className="flex size-[560px] min-w-[360px] flex-col gap-6 overflow-hidden rounded-xl border border-[rgba(9,9,11,0.2)] bg-white p-6">
            <div className="flex w-full max-w-[460px] flex-col gap-2">
              <p className="text-2xl font-semibold leading-8 text-[#09090b]">Data-agnostic</p>
              <div className="text-base font-normal leading-6 text-[#71717a]">
                <p className="mb-2">All the data is separate from components so you can edit it in seconds or make it dynamic.</p>
                <p>Easily connect to a CMS of your choice.</p>
              </div>
            </div>
            <div className="relative min-h-px flex-1">
              <Image src="/landing/illustrations/ripple.svg" alt="" fill className="object-contain" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
