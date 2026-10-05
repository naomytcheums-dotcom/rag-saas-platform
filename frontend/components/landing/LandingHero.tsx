import Image from "next/image";

export default function LandingHero() {
  return (
    <div className="relative isolate flex flex-col items-center gap-24 bg-white px-8 pb-0 pt-20">
      <div className="z-[2] flex w-full flex-col items-center gap-12">
        <div className="flex items-center gap-2 rounded-full border border-[rgba(9,9,11,0.2)] px-2.5 py-1">
          <p className="text-xs font-semibold leading-4 text-[#71717a]">New version of Launch UI is out!</p>
          <a
            href="https://www.mikolajdobrucki.com/jupiter?ref=figma"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1"
          >
            <p className="text-xs font-semibold leading-4 text-[#09090b]">Read more</p>
            <Image src="/landing/icons/arrow-right.svg" alt="" width={12} height={12} className="size-3" />
          </a>
        </div>

        <p
          className="w-[1248px] max-w-full bg-clip-text text-center text-[96px] font-semibold leading-none text-transparent"
          style={{ backgroundImage: "linear-gradient(110deg, rgb(9,9,11) 24.451%, rgb(113,113,122) 73.781%)" }}
        >
          Give your big idea the website it deserves
        </p>
        <p className="w-[544px] max-w-full text-center text-xl font-medium leading-7 text-[#71717a]">
          Landing page kit template with React, Shadcn/ui and Tailwind that you can copy/paste into your project.
        </p>

        <div className="flex items-start gap-4">
          <a
            href="https://www.launchuicomponents.com/#subscribe"
            target="_blank"
            rel="noreferrer"
            className="rounded-md bg-gradient-to-b from-[#18181b] to-[rgba(9,9,11,0.8)] px-4 py-2 text-sm font-medium text-[#fafafa] shadow-[0px_1px_2px_0px_rgba(0,0,0,0.1),0px_1px_3px_0px_rgba(0,0,0,0.1)]"
          >
            Get started
          </a>
          <a
            href="https://github.com/launch-ui/launch-ui"
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-[rgba(9,9,11,0.2)] bg-gradient-to-t from-[rgba(9,9,11,0.05)] to-[rgba(9,9,11,0.1)] px-4 py-2 text-sm font-medium text-[#09090b]"
          >
            Github
          </a>
        </div>
      </div>

      <div className="relative z-[1] w-[1248px] max-w-full">
        <div className="pointer-events-none absolute -left-[217px] -right-[248px] -top-[285px] h-[1069px]">
          <Image src="/landing/illustrations/glows.svg" alt="" fill className="object-contain" />
        </div>
        <div className="relative flex flex-col items-start rounded-2xl bg-[rgba(9,9,11,0.05)] px-2 pt-2">
          <div className="relative aspect-[1232/753] w-full rounded-lg border border-white">
            <div className="absolute inset-0 overflow-hidden rounded-lg">
              <Image src="/landing/illustrations/hero-screenshot.png" alt="" fill className="object-cover" />
            </div>
          </div>
        </div>
        <div
          className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3"
          style={{ backgroundImage: "linear-gradient(to bottom, rgba(255,255,255,0) 0%, rgba(255,255,255,0.9) 85.5%)" }}
        />
      </div>
    </div>
  );
}
