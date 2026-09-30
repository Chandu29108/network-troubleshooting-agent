import * as Sentry from "@sentry/nextjs";

// This is what actually catches things like a crashed React component or a
// fetch() to the backend that threw — the errors a user sees in their
// browser console that the backend's own Sentry setup never sees, since
// they never reached the server.
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || undefined,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT || "development",
  tracesSampleRate: 0.1,
  // Session replay is off by default — it records real DOM snapshots of
  // what the user saw, which is more than this project needs to capture,
  // and adds its own tracking-consent considerations. Can be turned on
  // later (Sentry.replayIntegration()) if it turns out to be useful.
});
