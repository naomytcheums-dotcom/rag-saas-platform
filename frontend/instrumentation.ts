// Phase 5, Étape 15 -- server/edge-side error tracking, using Next.js's
// own instrumentation-hook convention. NOT `sentry.server.config.ts`/
// `sentry.edge.config.ts` (this étape's own spec pseudocode used those,
// but they're the SDK's OLD pattern): @sentry/nextjs's build plugin
// (node_modules/@sentry/nextjs/build/cjs/config/webpack.js,
// `warnAboutDeprecatedConfigFiles`) explicitly warns that Sentry.init
// must be called inside `register()` of a real Next.js instrumentation
// file, and separately warns (`warnAboutMissingOnRequestErrorHandler`)
// when `onRequestError` isn't exported here -- both addressed below,
// not left as a silent build-time warning.

import * as Sentry from "@sentry/nextjs";

export async function register() {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  const environment = process.env.NEXT_PUBLIC_ENVIRONMENT ?? "development";

  if (process.env.NEXT_RUNTIME === "nodejs" || process.env.NEXT_RUNTIME === "edge") {
    Sentry.init({ dsn, environment, tracesSampleRate: 0.1 });
  }
}

export const onRequestError = Sentry.captureRequestError;
