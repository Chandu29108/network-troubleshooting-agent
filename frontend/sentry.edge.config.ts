import * as Sentry from "@sentry/nextjs";

// Covers errors thrown in middleware.ts (the Clerk route-protection
// middleware runs on the Edge runtime, separate from the Node server).
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || undefined,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT || "development",
  tracesSampleRate: 0.1,
});
