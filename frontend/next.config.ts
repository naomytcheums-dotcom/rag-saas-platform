import type { NextConfig } from "next";
// `@sentry/nextjs/config`, not the package root -- this SDK version
// (`@sentry/nextjs@^11`) only exports `withSentryConfig` from this
// subpath (verified against node_modules/@sentry/nextjs/package.json's
// own `exports` map; the root export has no such member).
import { withSentryConfig } from "@sentry/nextjs/config";

const nextConfig: NextConfig = {
  // The "N" badge a user reported seeing bottom-left is Next.js's own
  // dev-mode indicator (shown only under `next dev`, never in a
  // production build) -- not a real app bug, but disabled here so the
  // dev preview matches production and doesn't read as unfinished UI.
  devIndicators: false,
};

// Phase 5, Étape 15 -- wraps the config with Sentry's build-time
// behavior (webpack/turbopack instrumentation + sourcemap upload).
// `org`/`project`/`authToken` (SENTRY_AUTH_TOKEN) are only needed for
// the sourcemap-upload step -- same "real code, off unless configured"
// pattern as everywhere else Sentry touches this codebase: without
// them, the build still succeeds, it just skips uploading sourcemaps
// (a real Sentry SDK behavior, not something this config fakes).
export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  silent: true,
  widenClientFileUpload: true,
  // Renamed from this étape's own spec pseudocode's `hideSourceMaps` --
  // verified against this SDK version's own SentryBuildOptions type
  // (node_modules/@sentry/nextjs/build/types/config/types.d.ts).
  sourcemaps: { deleteSourcemapsAfterUpload: true },
});
