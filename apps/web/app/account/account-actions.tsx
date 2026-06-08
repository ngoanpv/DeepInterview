"use client";

import {
  checkoutUrl,
  manageSubscriptionUrl,
  type CheckoutTarget,
} from "@/lib/billing";
import { CREDIT_PACKS } from "@/lib/plan";
import { Button } from "@/components/ui/button";

/**
 * Client island for the account page: gated upgrade / buy-credit / manage links.
 * `checkoutUrl` reads NEXT_PUBLIC_* (inlined client-side); null → render a
 * disabled self-host fallback rather than a dead link.
 */
export function AccountActions({ plan }: { plan: string }) {
  const upgradeTarget: CheckoutTarget =
    plan === "pro"
      ? { kind: "plan", plan: "career", cycle: "monthly" }
      : { kind: "plan", plan: "pro", cycle: "monthly" };
  const upgradeHref = checkoutUrl(upgradeTarget);
  const manageHref = manageSubscriptionUrl();
  const upgradeLabel = plan === "pro" ? "Upgrade to Career" : "Upgrade to Pro";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        {plan !== "career" &&
          (upgradeHref ? (
            <a href={upgradeHref} className="no-underline">
              <Button size="md">{upgradeLabel}</Button>
            </a>
          ) : (
            <Button
              size="md"
              disabled
              title="Configure Paddle to enable checkout"
            >
              Self-host free / configure Paddle
            </Button>
          ))}

        {manageHref ? (
          <a href={manageHref} className="no-underline">
            <Button variant="out" size="md">
              Manage subscription
            </Button>
          </a>
        ) : (
          <Button variant="out" size="md" disabled>
            Manage subscription
          </Button>
        )}
      </div>

      <div>
        <p className="text-[13px] text-muted">
          Buy interview credits (never expire)
        </p>
        <div className="mt-2 flex flex-wrap gap-3">
          {CREDIT_PACKS.map((pack) => {
            const href = checkoutUrl({
              kind: "pack",
              pack: pack.id as "pack_5" | "pack_20",
            });
            const label = `$${pack.price_usd} · ${pack.name}`;
            return href ? (
              <a key={pack.id} href={href} className="no-underline">
                <Button variant="out" size="md">
                  {label}
                </Button>
              </a>
            ) : (
              <Button key={pack.id} variant="out" size="md" disabled>
                {label}
              </Button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
