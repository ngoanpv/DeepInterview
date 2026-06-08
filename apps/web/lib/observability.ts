/**
 * WP-12 — gated, provider-agnostic observability for the web app.
 *
 * Design goals (see docs/DEPLOY.md):
 *   - ZERO config = clean no-op. With no SENTRY_DSN / NEXT_PUBLIC_SENTRY_DSN
 *     set, nothing initializes and nothing is imported.
 *   - `@sentry/nextjs` is INTENTIONALLY NOT a dependency. We must never let
 *     `tsc --noEmit` or `next build` try to resolve it statically, so the
 *     import specifier is assembled at runtime (non-literal) and wrapped in a
 *     try/catch. If the package is absent, init is a silent no-op.
 *   - Never throws: a broken/missing tracer must not take down a request.
 *
 * To actually wire Sentry, install `@sentry/nextjs` and set a DSN; this module
 * then dynamically loads and initializes it. Swap the provider here to stay
 * provider-agnostic without touching call sites.
 */

let initialized = false;

/** A DSN from either the server or public env enables observability. */
function resolveDsn(): string | undefined {
  return (
    process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN || undefined
  );
}

/** True only when a DSN is configured. */
export function isObservabilityEnabled(): boolean {
  return Boolean(resolveDsn());
}

/**
 * Initialize observability if (and only if) a DSN is set AND the optional
 * `@sentry/nextjs` package is installed. No-op otherwise. Safe to call
 * multiple times (e.g. from Next's `register()` hook).
 */
export async function initObservability(): Promise<void> {
  if (initialized) return;
  const dsn = resolveDsn();
  if (!dsn) return; // gated: no DSN ⇒ no-op, no import attempted.

  try {
    // Non-literal specifier: keeps tsc + webpack from resolving an
    // uninstalled module at build time. The catch makes a missing package a
    // clean no-op at runtime.
    const moduleName = ["@sentry", "nextjs"].join("/");
    const sentry: unknown = await import(/* webpackIgnore: true */ moduleName);
    const mod = sentry as { init?: (opts: Record<string, unknown>) => void };
    if (typeof mod.init === "function") {
      mod.init({
        dsn,
        tracesSampleRate: Number(
          process.env.SENTRY_TRACES_SAMPLE_RATE ?? "0.1",
        ),
        environment: process.env.NODE_ENV ?? "production",
      });
      initialized = true;
    }
  } catch {
    // Package not installed or failed to load — stay a no-op.
  }
}

/**
 * Report an error to the configured provider if available; otherwise log to the
 * console. Always safe to call; never throws.
 */
export async function captureError(error: unknown): Promise<void> {
  if (isObservabilityEnabled()) {
    try {
      const moduleName = ["@sentry", "nextjs"].join("/");
      const sentry: unknown = await import(
        /* webpackIgnore: true */ moduleName
      );
      const mod = sentry as { captureException?: (e: unknown) => void };
      if (typeof mod.captureException === "function") {
        mod.captureException(error);
        return;
      }
    } catch {
      // fall through to console.
    }
  }
  // Default sink: structured console so logs are still useful with no provider.
  console.error("[observability] captureError", error);
}
