// Phase 5, Étape 15 -- frontend error tracking, same "real code, off
// unless configured" pattern as api/security/error_tracking.py's own
// setup_error_tracking (Étape 7): initializing with an empty DSN is
// itself a documented Sentry no-op, but NEXT_PUBLIC_SENTRY_DSN being
// unset here is honest and inert, never a placeholder. Session Replay
// is opt-in-safe by construction: maskAllText/blockAllMedia are on
// unconditionally, so a session replay can never leak a user's own
// document content or PII even before any server-side redaction runs.
//
// `instrumentation-client.ts` (Next.js's own file convention), not
// `sentry.client.config.ts` -- @sentry/nextjs itself deprecates that
// file under Turbopack (this app's own dev/build runtime, confirmed by
// `next dev`'s own "(Turbopack)" banner): the SDK's build plugin
// (node_modules/@sentry/nextjs/build/cjs/config/webpack.js) emits an
// explicit warning that `sentry.client.config.ts` "will no longer
// work" there, and points at this exact replacement.

import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT ?? "development",
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
  integrations: [
    Sentry.replayIntegration({
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
});
