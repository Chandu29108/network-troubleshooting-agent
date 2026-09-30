import * as Sentry from "@sentry/nextjs";

// Same DSN as the client build (NEXT_PUBLIC_SENTRY_DSN) — Sentry tells
// server vs. browser errors apart by which SDK reported them, not by a
// different key. Empty string just means "disabled", same as the backend.
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || undefined,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT || "development",
  tracesSampleRate: 0.1,
});
