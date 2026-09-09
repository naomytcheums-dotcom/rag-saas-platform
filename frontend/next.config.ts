import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The "N" badge a user reported seeing bottom-left is Next.js's own
  // dev-mode indicator (shown only under `next dev`, never in a
  // production build) -- not a real app bug, but disabled here so the
  // dev preview matches production and doesn't read as unfinished UI.
  devIndicators: false,
};

export default nextConfig;
