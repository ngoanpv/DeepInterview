/**
 * WP-12 — Next.js instrumentation hook.
 *
 * Next calls `register()` once when the server starts. We use it to (gated)
 * initialize observability. With no SENTRY_DSN this is a clean no-op, so
 * `next build` stays green even though `@sentry/nextjs` is NOT installed
 * (see apps/web/lib/observability.ts).
 *
 * https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */

export async function register(): Promise<void> {
  // Server runtime only — skip Edge so we don't pull node-only providers there.
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { initObservability } = await import("./lib/observability");
    await initObservability();
  }
}
