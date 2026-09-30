/**
 * Runs once when the Next.js server starts (both the Node.js server runtime
 * and the Edge runtime, e.g. middleware) — this is where Sentry needs to be
 * initialized for anything that happens outside the browser. Client-side
 * init lives separately in instrumentation-client.ts, since that runs in a
 * different environment on a different schedule.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

export const onRequestError = async (
  ...args: Parameters<Required<typeof import("@sentry/nextjs")>["captureRequestError"]>
) => {
  const Sentry = await import("@sentry/nextjs");
  Sentry.captureRequestError(...args);
};
