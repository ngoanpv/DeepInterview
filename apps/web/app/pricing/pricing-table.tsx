"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import { PLANS, PLAN_ORDER, CREDIT_PACKS, type PlanId } from "@/lib/plan";
import { checkoutUrl, type CheckoutTarget } from "@/lib/billing";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

/**
 * Client island: holds the monthly/annual toggle state and renders the three
 * tiers + credit-pack row. Checkout links are resolved through `checkoutUrl`
 * (gated) — when Paddle is unconfigured the CTA shows the self-host fallback.
 */
export function PricingTable() {
  const [annual, setAnnual] = useState(false);

  return (
    <div className="flex flex-col gap-10">
      {/* Billing-cycle toggle */}
      <div className="flex items-center justify-center gap-3">
        <span
          className={cn(
            "text-[13px]",
            annual ? "text-muted" : "text-ink font-medium",
          )}
        >
          Monthly
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={annual}
          aria-label="Toggle annual billing"
          onClick={() => setAnnual((v) => !v)}
          className={cn(
            "relative h-6 w-11 rounded-full border transition-colors",
            annual ? "border-accent bg-accent" : "border-line bg-panel",
          )}
        >
          <span
            className={cn(
              "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
              annual ? "translate-x-[22px]" : "translate-x-0.5",
            )}
          />
        </button>
        <span
          className={cn(
            "text-[13px]",
            annual ? "text-ink font-medium" : "text-muted",
          )}
        >
          Annual
        </span>
        <Badge variant="ok" className="ml-1">
          Save ~20%
        </Badge>
      </div>

      {/* Three tiers */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {PLAN_ORDER.map((id) => (
          <TierCard key={id} id={id} annual={annual} />
        ))}
      </div>

      {/* Credit packs */}
      <CreditPackRow />
    </div>
  );
}

function priceLabel(id: PlanId, annual: boolean): { big: string; sub: string } {
  const plan = PLANS[id];
  if (plan.price_usd === 0) return { big: "$0", sub: "forever" };
  if (annual && plan.price_annual_usd != null) {
    const perMonth = Math.round(plan.price_annual_usd / 12);
    return {
      big: `$${perMonth}`,
      sub: `/mo · billed $${plan.price_annual_usd}/yr`,
    };
  }
  return { big: `$${plan.price_usd}`, sub: "/month" };
}

function TierCard({ id, annual }: { id: PlanId; annual: boolean }) {
  const plan = PLANS[id];
  const popular = Boolean(plan.popular);
  const { big, sub } = priceLabel(id, annual);

  // Resolve a checkout target for the paid tiers.
  let target: CheckoutTarget | null = null;
  if (id === "pro") {
    target = {
      kind: "plan",
      plan: "pro",
      cycle: annual ? "annual" : "monthly",
    };
  } else if (id === "career") {
    target = { kind: "plan", plan: "career", cycle: "monthly" };
  }
  const href = target ? checkoutUrl(target) : null;

  return (
    <Card className={cn("flex flex-col p-6", popular && "ring-1 ring-accent")}>
      <div className="flex items-center gap-2">
        <h3 className="serif text-2xl text-ink">{plan.name}</h3>
        {popular && <Badge variant="accent">Most Popular</Badge>}
      </div>

      <div className="mt-3 flex items-baseline gap-1.5">
        <span className="serif text-4xl text-ink">{big}</span>
        <span className="text-[13px] text-muted">{sub}</span>
      </div>

      {id === "career" && plan.lifetime_usd != null && (
        <p className="mt-1 text-[12px] text-accent">
          or ${plan.lifetime_usd} lifetime — best value
        </p>
      )}

      <p className="mt-3 text-[13px] text-muted">
        {plan.interviews_per_month} voice interviews / month
      </p>

      <ul className="mt-5 flex flex-1 flex-col gap-2.5">
        {plan.features.map((f) => (
          <li
            key={f}
            className="flex items-start gap-2 text-[13.5px] text-ink-soft"
          >
            <Check
              className="mt-0.5 h-4 w-4 shrink-0 text-accent"
              aria-hidden
            />
            {f}
          </li>
        ))}
      </ul>

      <div className="mt-6">
        {id === "free" ? (
          <a href="/setup" className="block no-underline">
            <Button variant="out" size="lg" className="w-full">
              Start free
            </Button>
          </a>
        ) : href ? (
          <a href={href} className="block no-underline">
            <Button
              variant={popular ? "ink" : "out"}
              size="lg"
              className="w-full"
            >
              Choose {plan.name}
            </Button>
          </a>
        ) : (
          // Paddle unconfigured → honest self-host fallback (no dead checkout).
          <Button
            variant={popular ? "ink" : "out"}
            size="lg"
            className="w-full"
            disabled
            title="Configure Paddle to enable hosted checkout"
          >
            Self-host free / configure Paddle
          </Button>
        )}
      </div>
    </Card>
  );
}

function CreditPackRow() {
  return (
    <Card className="flex flex-col gap-4 p-6 md:flex-row md:items-center md:justify-between">
      <div>
        <h3 className="serif text-xl text-ink">Interview credits</h3>
        <p className="mt-1 text-[13px] text-muted">
          Top up any plan. Credits never expire — perfect for a burst around an
          active job search.
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        {CREDIT_PACKS.map((pack) => {
          const href = checkoutUrl({
            kind: "pack",
            pack: pack.id as "pack_5" | "pack_20",
          });
          const inner = (
            <span className="flex items-baseline gap-2">
              <span className="font-medium text-ink">${pack.price_usd}</span>
              <span className="text-[13px] text-muted">{pack.name}</span>
            </span>
          );
          return href ? (
            <a key={pack.id} href={href} className="no-underline">
              <Button variant="out" size="md">
                {inner}
              </Button>
            </a>
          ) : (
            <Button key={pack.id} variant="out" size="md" disabled>
              {inner}
            </Button>
          );
        })}
      </div>
    </Card>
  );
}
