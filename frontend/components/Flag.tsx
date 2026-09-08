"use client";

import * as Flags from "country-flag-icons/react/3x2";

interface FlagProps {
  country: string;
  label: string;
  size?: number;
}

// Real SVG flags (country-flag-icons, MIT), not emoji -- found and
// fixed directly from user feedback: Unicode flag emoji render as
// plain "FR"/"US" text on Windows instead of real flag images (a real,
// documented Windows font limitation), so every language picker in
// this app now renders a real, crisp SVG flag instead, with a real
// accessible label (never bare, unlabeled color).
export default function Flag({ country, label, size = 20 }: FlagProps) {
  const FlagComponent = (Flags as unknown as Record<string, React.ComponentType<{ title?: string; className?: string }>>)[country];
  if (!FlagComponent) return null;

  return (
    <span role="img" aria-label={label} title={label} className="inline-block overflow-hidden rounded-sm shadow-sm" style={{ width: size, height: size * (2 / 3) }}>
      <FlagComponent className="h-full w-full" />
    </span>
  );
}
