import Image from "next/image";

const ITEMS = [
  { icon: "scan-face", title: "Accessibility first", desc: "Fully WCAG 2.0 compliment, made with best a11y practices" },
  { icon: "monitor-smartphone", title: "Responsive design", desc: "Looks and works great on any device and screen size" },
  { icon: "eclipse", title: "Light and dark mode", desc: "Seamless switching between color schemes, 6 themes included" },
  { icon: "blocks", title: "Easy to customize", desc: "Flexible options to match your  product or brand" },
  { icon: "fast-forward", title: "Top-level performance ", desc: "Made for lightning-fast load times and smooth interactions" },
  { icon: "rocket", title: "Production ready", desc: "Thoroughly tested and launch-prepared" },
  { icon: "languages", title: "Made for localisation", desc: "Easy to implement support for multiple languages and regions" },
  { icon: "square-pen", title: "CMS friendly", desc: "Built to work with your any headless content management system" },
];

export default function LandingItems() {
  return (
    <div className="mx-auto flex w-full max-w-[1312px] flex-col items-center gap-20 bg-white px-8 py-20">
      <p className="text-center text-5xl font-semibold leading-none text-[#09090b]">
        Everything you need.
        <br />
        Nothing you don&apos;t.
      </p>
      <div className="flex w-full flex-wrap items-start gap-12">
        {ITEMS.map((item) => (
          <div key={item.title} className="flex min-w-[240px] flex-1 flex-col gap-2">
            <div className="flex w-full items-center gap-2">
              <Image src={`/landing/icons/${item.icon}.svg`} alt="" width={24} height={24} className="size-6" />
              <p className="flex-1 text-lg font-semibold leading-7 text-[#09090b]">{item.title}</p>
            </div>
            <p className="w-full text-base font-normal leading-6 text-[#71717a]">{item.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
