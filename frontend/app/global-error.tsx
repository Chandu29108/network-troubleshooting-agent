"use client";

import * as Sentry from "@sentry/nextjs";
import NextError from "next/error";
import { useEffect } from "react";

/**
 * Next.js's App Router doesn't report an error thrown in the root layout
 * itself to Sentry automatically (regular error.tsx boundaries only cover
 * errors below them in the tree) — this file is what closes that gap.
 * Falls back to Next's own default error page for what the user sees.
 */
export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html>
      <body>
        <NextError statusCode={0} />
      </body>
    </html>
  );
}
