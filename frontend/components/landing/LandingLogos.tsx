import Image from "next/image";

const LOGOS = [
  { icon: "logo-figma", name: "Figma", version: null },
  { icon: "logo-react", name: "React.js", version: "18.3.1" },
  { icon: "logo-typescript", name: "Typescript", version: "5.6.2" },
  { icon: "logo-shadcn", name: "Shadcn", version: "2.0.7" },
  { icon: "logo-tailwind", name: "Tailwind CSS", version: "3.4.11" },
];

export default function LandingLogos() {
  return (
    <div className="mx-auto flex w-full max-w-[1312px] flex-col items-center gap-12 bg-white px-8 py-20">
      <p className="text-sm font-semibold leading-5 text-[#09090b]">Built with the best tools</p>
      <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6">
        {LOGOS.map((logo) => (
          <div key={logo.name} className="flex items-center gap-2">
            <Image src={`/landing/icons/${logo.icon}.svg`} alt="" width={24} height={24} className="size-6" />
            <p className="text-sm font-medium leading-5 text-[#09090b]">{logo.name}</p>
            {logo.version && <p className="text-sm font-medium leading-5 text-[#71717a]">{logo.version}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
