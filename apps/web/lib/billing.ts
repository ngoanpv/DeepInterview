/**
 * Billing integration (WP-11) — Paddle as merchant-of-record, via REST/fetch
 * (no SDK, no new deps). EVERY path is gated on env: with no keys configured
 * the app still builds and renders and checkout URLs come back `null`. Never
 * throw at import time.
 *
 * This module is CLIENT-SAFE: it only reads NEXT_PUBLIC_* config and the
 * server-only PADDLE_* env *values* (which are simply undefined client-side).
 * It imports no Node built-ins, so the pricing/account client islands can import
 * `checkoutUrl` directly. The HMAC webhook verification (which needs node:crypto)
 * lives in the server-only `lib/billing-server.ts`.
 */

import type { PlanId } from "@/lib/plan";

// ── env (gated, lazy) ───────────────────────────────────────────────────────

/** Server-only Paddle config. */
const paddleServerEnv = {
  get apiKey(): string | undefined {
    return process.env.PADDLE_API_KEY || undefined;
  },
  get webhookSecret(): string | undefined {
    return process.env.PADDLE_WEBHOOK_SECRET || undefined;
  },
};

/**
 * "sandbox" | "production" — drives the hosted-checkout host. MUST be a static
 * NEXT_PUBLIC_* ref: `checkoutUrl` runs inside client islands, where non-public
 * env is `undefined`. Defaults to sandbox so an unset value never bills live.
 */
function paddleEnvironment(): string {
  return process.env.NEXT_PUBLIC_PADDLE_ENV || "sandbox";
}

/**
 * Public Paddle config — static NEXT_PUBLIC_* literals so they are inlined
 * client-side (dynamic indexing of process.env is undefined in the browser).
 * Each price id maps a plan/pack to a Paddle catalog price.
 */
export const paddlePublicEnv = {
  get clientToken(): string | undefined {
    return process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN || undefined;
  },
  get priceProMonthly(): string | undefined {
    return process.env.NEXT_PUBLIC_PADDLE_PRICE_PRO_MONTHLY || undefined;
  },
  get priceProAnnual(): string | undefined {
    return process.env.NEXT_PUBLIC_PADDLE_PRICE_PRO_ANNUAL || undefined;
  },
  get priceCareerMonthly(): string | undefined {
    return process.env.NEXT_PUBLIC_PADDLE_PRICE_CAREER_MONTHLY || undefined;
  },
  get priceCareerLifetime(): string | undefined {
    return process.env.NEXT_PUBLIC_PADDLE_PRICE_CAREER_LIFETIME || undefined;
  },
  get pricePack5(): string | undefined {
    return process.env.NEXT_PUBLIC_PADDLE_PRICE_PACK_5 || undefined;
  },
  get pricePack20(): string | undefined {
    return process.env.NEXT_PUBLIC_PADDLE_PRICE_PACK_20 || undefined;
  },
};

/** True when the client-side checkout (token + at least one price) is wired. */
export function isPaddleClientConfigured(): boolean {
  return Boolean(
    paddlePublicEnv.clientToken && paddlePublicEnv.priceProMonthly,
  );
}

/** True when the server-side Paddle API key is present. */
export function isPaddleServerConfigured(): boolean {
  return Boolean(paddleServerEnv.apiKey);
}

/** True when webhook signatures can be verified. */
export function isPaddleWebhookConfigured(): boolean {
  return Boolean(paddleServerEnv.webhookSecret);
}

// ── checkout ────────────────────────────────────────────────────────────────

export type CheckoutTarget =
  | {
      kind: "plan";
      plan: Exclude<PlanId, "free">;
      cycle: "monthly" | "annual" | "lifetime";
    }
  | { kind: "pack"; pack: "pack_5" | "pack_20" };

export interface CheckoutUser {
  id?: string | null;
  email?: string | null;
}

/** Resolve the Paddle price id for a checkout target (or undefined). */
function priceIdFor(target: CheckoutTarget): string | undefined {
  if (target.kind === "pack") {
    return target.pack === "pack_5"
      ? paddlePublicEnv.pricePack5
      : paddlePublicEnv.pricePack20;
  }
  if (target.plan === "pro") {
    return target.cycle === "annual"
      ? paddlePublicEnv.priceProAnnual
      : paddlePublicEnv.priceProMonthly;
  }
  // career
  return target.cycle === "lifetime"
    ? paddlePublicEnv.priceCareerLifetime
    : paddlePublicEnv.priceCareerMonthly;
}

/**
 * Build a hosted-checkout URL for a plan or credit pack, or `null` when Paddle
 * is not configured (the CTA then falls back to "Self-host free / configure
 * Paddle"). We pass the catalog price id and prefill the customer; Paddle's
 * overlay/hosted checkout reads `_ptxn`-style params. This returns a deep link
 * to Paddle-hosted checkout which works without the JS SDK.
 */
export function checkoutUrl(
  target: CheckoutTarget,
  user?: CheckoutUser,
): string | null {
  if (!isPaddleClientConfigured()) return null;
  const priceId = priceIdFor(target);
  if (!priceId) return null;

  const host =
    paddleEnvironment() === "production"
      ? "https://buy.paddle.com"
      : "https://sandbox-buy.paddle.com";

  const params = new URLSearchParams();
  params.set("items[0][priceId]", priceId);
  params.set("items[0][quantity]", "1");
  if (user?.email) params.set("customer[email]", user.email);
  if (user?.id) params.set("customData[user_id]", user.id);

  return `${host}/checkout?${params.toString()}`;
}

/** Paddle "manage subscription" / customer portal entry point. */
export function manageSubscriptionUrl(): string | null {
  if (!isPaddleClientConfigured()) return null;
  const host =
    paddleEnvironment() === "production"
      ? "https://buy.paddle.com"
      : "https://sandbox-buy.paddle.com";
  return `${host}/portal`;
}

// Webhook signature verification needs node:crypto, which must NOT be bundled
// into client islands that import `checkoutUrl` from this module. It therefore
// lives in the server-only `lib/billing-server.ts`. We expose the raw secret
// reader here so that module can read it through one accessor.
/** Server-only: the Paddle webhook secret (undefined when unset). */
export function paddleWebhookSecret(): string | undefined {
  return paddleServerEnv.webhookSecret;
}

// ── regional payment rails (gated stubs — NOT implemented) ───────────────────
//
// Vietnam (the beachhead) sits in PPP T3–T4; local rails convert far better than
// cards. These are intentionally unimplemented stubs, gated on env, so the
// surface exists without shipping a half-built integration.
//
//   MoMo   — env: MOMO_PARTNER_CODE (+ access key / secret). REST: create order,
//            redirect to MoMo, verify IPN signature. TODO: implement.
//   VNPay  — env: VNPAY_TMN_CODE (+ hash secret). Build vnp_* query, HMAC-SHA512
//            sign, redirect to VNPay sandbox/prod, verify return signature. TODO.

export function isMomoConfigured(): boolean {
  return Boolean(process.env.MOMO_PARTNER_CODE);
}

export function isVnpayConfigured(): boolean {
  return Boolean(process.env.VNPAY_TMN_CODE);
}

/** Stub: build a MoMo checkout URL. Returns null until the rail is implemented. */
export function momoCheckoutUrl(_target: CheckoutTarget): string | null {
  // TODO(regional-rails): implement MoMo create-order + redirect.
  return null;
}

/** Stub: build a VNPay checkout URL. Returns null until the rail is implemented. */
export function vnpayCheckoutUrl(_target: CheckoutTarget): string | null {
  // TODO(regional-rails): implement VNPay vnp_* signing + redirect.
  return null;
}
