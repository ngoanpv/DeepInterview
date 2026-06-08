/**
 * Server-only billing helpers (WP-11) — the parts that need Node built-ins
 * (node:crypto for HMAC). Kept OUT of `lib/billing.ts` so client islands that
 * import `checkoutUrl` never pull `node:crypto` into the browser bundle.
 *
 * Import this only from route handlers / server code. Gated on env: with no
 * webhook secret, verification fails closed.
 */

// NOTE: this module imports node:crypto — import it ONLY from server code
// (route handlers / server components). Do not import it from a "use client"
// file or node:crypto will be pulled into the browser bundle and the build
// will fail. (We'd use the `server-only` package as a guard, but it isn't a
// dependency here.)
import crypto from "node:crypto";
import { paddleWebhookSecret } from "@/lib/billing";

/**
 * Verify a Paddle Billing webhook signature.
 *
 * Paddle sends `Paddle-Signature: ts=<unix>;h1=<hex-hmac>`. The signed payload
 * is `<ts>:<raw-body>`, HMAC-SHA256'd with the webhook secret. Returns false
 * (reject) whenever the secret is unconfigured or the signature does not match
 * — fail closed.
 */
export function verifyPaddleWebhook(
  signatureHeader: string | null | undefined,
  rawBody: string,
): boolean {
  const secret = paddleWebhookSecret();
  if (!secret || !signatureHeader) return false;

  // Parse "ts=...;h1=..."
  const parts = signatureHeader
    .split(";")
    .reduce<Record<string, string>>((acc, kv) => {
      const [k, v] = kv.split("=");
      if (k && v) acc[k.trim()] = v.trim();
      return acc;
    }, {});
  const ts = parts.ts;
  const h1 = parts.h1;
  if (!ts || !h1) return false;

  const expected = crypto
    .createHmac("sha256", secret)
    .update(`${ts}:${rawBody}`)
    .digest("hex");

  // Constant-time compare; guard against length mismatch (timingSafeEqual throws).
  let a: Buffer;
  let b: Buffer;
  try {
    a = Buffer.from(expected, "hex");
    b = Buffer.from(h1, "hex");
  } catch {
    return false;
  }
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}
