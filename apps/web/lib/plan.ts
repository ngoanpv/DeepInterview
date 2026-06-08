/**
 * Plan configuration + gating helpers (WP-11).
 *
 * Pure, env-free, isomorphic — safe to import from server actions, route
 * handlers, and client components. This is the single source of truth for the
 * per-tier interview caps. Golden rule 5: the cap on voice interviews is
 * enforced in code via `canStartInterview`; there is no literally-unlimited
 * voice plan here — every tier has a finite `interviews_per_month`.
 *
 * Denominate everything in INTERVIEWS, never tokens or minutes (pricing doc §5).
 */

export type PlanId = "free" | "pro" | "career";

export interface PlanConfig {
  id: PlanId;
  name: string;
  /** Monthly USD price (Tier-1 / full PPP). 0 for free. */
  price_usd: number;
  /** Per-year USD price when billed annually; null when not offered. */
  price_annual_usd: number | null;
  /** One-time lifetime USD price; null when not offered. */
  lifetime_usd: number | null;
  /** Hard fair-use cap on voice interviews per monthly period. Finite always. */
  interviews_per_month: number;
  /** Marketing bullet list. */
  features: string[];
  /** The hero/"Most Popular" tier. */
  popular?: boolean;
}

/**
 * The three consumer tiers (pricing doc §5). Caps per the WP-11 task spec
 * (free 3 / pro 10 / career 30 — the task overrides the doc's "Free = 1").
 */
export const PLANS: Record<PlanId, PlanConfig> = {
  free: {
    id: "free",
    name: "Free",
    price_usd: 0,
    price_annual_usd: null,
    lifetime_usd: null,
    interviews_per_month: 3,
    features: [
      "3 voice interviews / month",
      "Unlimited text feedback",
      "Full question bank",
      "CV + JD parsing",
      "1 study plan",
    ],
  },
  pro: {
    id: "pro",
    name: "Pro",
    price_usd: 19,
    // ~$15/mo billed annually (doc: $180/yr).
    price_annual_usd: 180,
    lifetime_usd: null,
    interviews_per_month: 10,
    popular: true,
    features: [
      "10 voice interviews / month",
      "Full study-coach loop",
      "Recordings + transcripts",
      "Premium voices",
      "Multilingual (10+ languages)",
      "No DeepInterview branding",
    ],
  },
  career: {
    id: "career",
    name: "Career",
    price_usd: 49,
    // Doc gives a $249 lifetime but no separate annual figure — leave annual
    // null and surface the lifetime price as Career's best-value line.
    price_annual_usd: null,
    lifetime_usd: 249,
    interviews_per_month: 30,
    features: [
      "30 voice interviews / month",
      "Priority processing",
      "Premium interviewer personas",
      "Everything in Pro",
    ],
  },
};

export const PLAN_ORDER: PlanId[] = ["free", "pro", "career"];

/** Non-expiring "interview" credit packs (overage / non-subscribers). */
export interface CreditPack {
  id: string;
  name: string;
  credits: number;
  price_usd: number;
}

export const CREDIT_PACKS: CreditPack[] = [
  { id: "pack_5", name: "5 interviews", credits: 5, price_usd: 15 },
  { id: "pack_20", name: "20 interviews", credits: 20, price_usd: 29 },
];

/** Regional purchasing-power-parity tiers (pricing doc §7). */
export interface PppTier {
  id: "T1" | "T2" | "T3" | "T4";
  label: string;
  /** Fractional discount vs Tier-1 (0 = full price). */
  discount: number;
  regions: string;
}

export const PPP_TIERS: PppTier[] = [
  {
    id: "T1",
    label: "Full",
    discount: 0,
    regions: "US, Canada, UK, W. Europe, Australia, Gulf",
  },
  {
    id: "T2",
    label: "-35%",
    discount: 0.35,
    regions: "Poland, Portugal, Mexico, Chile",
  },
  {
    id: "T3",
    label: "-60%",
    discount: 0.6,
    regions: "Brazil, Indonesia, Ukraine, Türkiye, South Africa",
  },
  {
    id: "T4",
    label: "-75%",
    discount: 0.75,
    regions: "India, Vietnam, Philippines, Nigeria, Egypt",
  },
];

/** Apply a PPP discount to a USD price, rounded to a charm-friendly value. */
export function pppPrice(usd: number, tier: PppTier): number {
  const raw = usd * (1 - tier.discount);
  return Math.round(raw * 100) / 100;
}

/**
 * The billing-relevant shape of a `profiles` row. Kept minimal and tolerant of
 * partial data so callers can pass a freshly-selected subset.
 */
export interface ProfileBilling {
  plan?: string | null;
  interviews_used?: number | null;
  credits?: number | null;
}

/** Normalize an arbitrary plan string to a known PlanId (defaults to free). */
export function normalizePlan(plan?: string | null): PlanId {
  return plan === "pro" || plan === "career" ? plan : "free";
}

/** The hard monthly interview cap for a plan. */
export function planCap(plan?: string | null): number {
  return PLANS[normalizePlan(plan)].interviews_per_month;
}

/**
 * Interviews the user may still start this period:
 *   cap − interviews_used (clamped ≥ 0)  +  non-expiring credits.
 * Credits cover overage once the metered cap is exhausted.
 */
export function remainingInterviews(profile: ProfileBilling): number {
  const cap = planCap(profile.plan);
  const used = Math.max(0, profile.interviews_used ?? 0);
  const credits = Math.max(0, profile.credits ?? 0);
  const withinCap = Math.max(0, cap - used);
  return withinCap + credits;
}

export type GateResult =
  | { allowed: true }
  | { allowed: false; reason: "out_of_interviews" };

/**
 * Golden rule 5 enforcement point. Allowed iff the user has at least one
 * interview left (metered headroom OR a credit). Pure — the caller decides
 * whether to even consult this (offline/dev bypasses it entirely).
 */
export function canStartInterview(profile: ProfileBilling): GateResult {
  return remainingInterviews(profile) > 0
    ? { allowed: true }
    : { allowed: false, reason: "out_of_interviews" };
}

/**
 * Whether starting the next interview should draw down a credit rather than the
 * metered cap. True once `interviews_used` has reached the plan cap (and a
 * credit is available). Used by the gate to decide what to decrement on success.
 */
export function shouldUseCredit(profile: ProfileBilling): boolean {
  const cap = planCap(profile.plan);
  const used = Math.max(0, profile.interviews_used ?? 0);
  const credits = Math.max(0, profile.credits ?? 0);
  return used >= cap && credits > 0;
}
