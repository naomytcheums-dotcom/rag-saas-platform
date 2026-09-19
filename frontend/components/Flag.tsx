"use client";

import { CN, DE, ES, FR, IT, JP, NL, PL, PT, RU, SA, US } from "country-flag-icons/react/3x2";

interface FlagProps {
  country: string;
  label: string;
  size?: number;
}

// Only the flags VOICE_LANGUAGES (lib/voiceConfig.ts) actually uses --
// `import * as Flags` used to pull in all 265 of this library's flag
// components into this route's bundle for the 12 this app can ever
// render. Add the matching named import here if VOICE_LANGUAGES grows.
const FLAGS: Record<string, React.ComponentType<{ title?: string; className?: string }>> = { CN, DE, ES, FR, IT, JP, NL, PL, PT, RU, SA, US };

// Real SVG flags (country-flag-icons, MIT), not emoji -- found and
// fixed directly from user feedback: Unicode flag emoji render as
// plain "FR"/"US" text on Windows instead of real flag images (a real,
// documented Windows font limitation), so every language picker in
// this app now renders a real, crisp SVG flag instead, with a real
// accessible label (never bare, unlabeled color).
export default function Flag({ country, label, size = 20 }: FlagProps) {
  const FlagComponent = FLAGS[country];
  if (!FlagComponent) return null;

  return (
    <span role="img" aria-label={label} title={label} className="inline-block overflow-hidden rounded-sm shadow-sm" style={{ width: size, height: size * (2 / 3) }}>
      <FlagComponent className="h-full w-full" />
    </span>
  );
}
