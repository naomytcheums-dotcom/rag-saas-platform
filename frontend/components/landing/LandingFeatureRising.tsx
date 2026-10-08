function IllustrationRisingLarge({ className }: { className?: string }) {
  return (
    <div className={className ?? "relative h-[568px] w-[1280px]"}>
      <div className="absolute -left-[217px] -right-[216px] -top-[285px] h-[1069px] overflow-clip">
        <div className="absolute left-[375px] top-[298px] h-[289px] w-[963px]">
          <div className="absolute -inset-x-[32.4%] -inset-y-[107.96%]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img alt="" className="block size-full max-w-none" src="/landing/illustrations/ellipse1.svg" />
          </div>
        </div>
      </div>
      <div className="absolute left-[101px] right-[101px] -top-1 h-[539px]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img alt="" className="absolute inset-0 block size-full max-w-none" src="/landing/illustrations/ellipse33.svg" />
      </div>
      <div className="absolute left-[101px] right-[101px] -top-1 h-[539px]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img alt="" className="absolute inset-0 block size-full max-w-none" src="/landing/illustrations/group5.svg" />
      </div>
      <div className="absolute left-[101px] right-[101px] -top-1 h-[539px]">
        <div className="absolute -inset-x-[6.17%] -top-[12.34%] -bottom-[11.87%]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img alt="" className="block size-full max-w-none" src="/landing/illustrations/ellipse32.svg" />
        </div>
      </div>
      <div
        className="absolute inset-x-0 bottom-0 h-[434px]"
        style={{ backgroundImage: "linear-gradient(to bottom, rgba(255,255,255,0) 0%, #ffffff 85.5%)" }}
      />
    </div>
  );
}

export default function LandingFeatureRising() {
  return (
    <div className="relative isolate flex flex-col items-center gap-24 bg-white px-8 pb-20 pt-32">
      <div className="z-[2] flex w-full flex-col items-center gap-12 text-center">
        <p
          className="w-[1248px] max-w-full bg-clip-text text-[72px] font-semibold leading-none text-transparent"
          style={{ backgroundImage: "linear-gradient(116deg, rgb(9,9,11) 24.451%, rgb(113,113,122) 73.781%)" }}
        >
          Quality you can trust.
          <br />
          And build on.
        </p>
        <p className="w-[580px] max-w-full text-xl font-medium leading-7 text-[#71717a]">
          You can trust that all of the designs are taking the full advantage of newest Figma&apos;s features and that
          code is written following best practices out there.
        </p>
      </div>
      <IllustrationRisingLarge className="relative z-[1] h-[535px] w-[1248px] max-w-full shrink-0" />
    </div>
  );
}
