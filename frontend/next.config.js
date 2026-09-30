const { withSentryConfig } = require("@sentry/nextjs/config");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
};

// withSentryConfig wraps the build to auto-instrument API routes and (when
// SENTRY_AUTH_TOKEN is set — optional, only needed for readable stack
// traces in production) upload source maps. With no token, everything
// still works; you just see minified stack traces in the Sentry UI instead
// of your original source lines.
module.exports = withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  silent: true,
  widenClientFileUpload: true,
  disableLogger: true,
  // Routes Sentry's browser requests through your own domain instead of
  // directly to sentry.io — avoids ad-blockers silently dropping error
  // reports for users who have one installed.
  tunnelRoute: "/monitoring",
});
