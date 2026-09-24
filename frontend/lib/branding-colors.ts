// Phase 5, Étape 15 -- small, real hex-color shading utility. Needed
// because app/globals.css's own `--accent-hover`/`--accent-soft` are
// fixed hex values, not computed from `--accent` -- overriding only
// `--accent` with an organization's own primary_color would leave a
// mismatched hover/soft state (e.g. a blue button that hovers orange),
// which is worse than not applying branding at all. These derive real,
// consistent hover/soft shades from whatever color the organization
// actually set, rather than leaving them stale.

function clamp(value: number): number {
  return Math.max(0, Math.min(255, value));
}

function parseHex(hex: string): [number, number, number] | null {
  const match = /^#?([0-9a-fA-F]{6})$/.exec(hex);
  if (!match) return null;
  const int = parseInt(match[1], 16);
  return [(int >> 16) & 255, (int >> 8) & 255, int & 255];
}

function toHex([r, g, b]: [number, number, number]): string {
  return `#${[r, g, b].map((v) => clamp(Math.round(v)).toString(16).padStart(2, "0")).join("")}`;
}

/** Darkens a hex color by `amount` (0-1) -- used for a hover state. */
export function darken(hex: string, amount: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  return toHex(rgb.map((c) => c * (1 - amount)) as [number, number, number]);
}

/** Lightens a hex color toward white by `amount` (0-1) -- used for a soft/tint background. */
export function lighten(hex: string, amount: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  return toHex(rgb.map((c) => c + (255 - c) * amount) as [number, number, number]);
}
