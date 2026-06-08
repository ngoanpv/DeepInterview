import type { Metadata } from "next";
import Link from "next/link";
import { Eyebrow } from "@/components/ui/eyebrow";
import { PPP_TIERS } from "@/lib/plan";
import { PricingTable } from "./pricing-table";

export const metadata: Metadata = {
  title: "Pricing — DeepInterview",
  description:
    "Free voice mock interviews + a Pro plan with 10 interviews/month. Open-source, self-hostable, multilingual.",
};

/**
 * Conversion page (WP-11). Server component shell + a small client island for
 * the annual toggle and gated checkout CTAs. Renders fully offline (no env).
 */
export default function PricingPage() {
  return (
    <main className="mx-auto max-w-[1040px] px-6 py-16">
      <div className="text-center">
        <Eyebrow>Pricing</Eyebrow>
        <h1 className="serif mx-auto mt-4 max-w-[18ch] text-5xl leading-[1.05] text-ink">
          Practice until the interview feels easy
        </h1>
        <p className="mx-auto mt-5 max-w-prose text-lg text-ink-soft">
          Start free. Upgrade when you want more voice interviews, the full
          study coach, and recordings. Cancel or pause anytime.
        </p>
      </div>

      <div className="mt-12">
        <PricingTable />
      </div>

      {/* Regional / PPP note */}
      <section className="mt-14">
        <h2 className="serif text-xl text-ink">Regional pricing</h2>
        <p className="mt-2 max-w-prose text-[14px] text-ink-soft">
          Prices adjust to local purchasing power. Pro starts around{" "}
          <span className="text-ink">$4.75/mo in Vietnam and India</span> and
          scales up to the full price in higher-income regions. PPP applies to
          consumer plans only; checkout requires a matching local payment
          method.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full max-w-[640px] border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="py-2 pr-4 font-medium">Tier</th>
                <th className="py-2 pr-4 font-medium">Discount</th>
                <th className="py-2 font-medium">Example regions</th>
              </tr>
            </thead>
            <tbody>
              {PPP_TIERS.map((tier) => (
                <tr key={tier.id} className="border-b border-line/60">
                  <td className="py-2 pr-4 font-mono text-ink">{tier.id}</td>
                  <td className="py-2 pr-4 text-ink-soft">{tier.label}</td>
                  <td className="py-2 text-muted">{tier.regions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Trust / FAQ-ish line */}
      <section className="mt-14 border-t border-line pt-8">
        <div className="grid grid-cols-1 gap-6 text-[14px] text-ink-soft md:grid-cols-3">
          <div>
            <h3 className="font-medium text-ink">Interviews, not tokens</h3>
            <p className="mt-1 text-[13px] text-muted">
              Plans are counted in whole voice interviews. No minutes, no token
              math, no bill shock.
            </p>
          </div>
          <div>
            <h3 className="font-medium text-ink">Credits never expire</h3>
            <p className="mt-1 text-[13px] text-muted">
              Job hunts are bursty. Buy a pack now, use it whenever your next
              search starts.
            </p>
          </div>
          <div>
            <h3 className="font-medium text-ink">Open-source forever</h3>
            <p className="mt-1 text-[13px] text-muted">
              The full core is AGPLv3 and{" "}
              <Link href="/setup">self-hostable</Link> with your own model keys
              — paid plans are managed convenience.
            </p>
          </div>
        </div>
        <p className="mt-8 text-center text-[12px] text-faint">
          Billing handled by Paddle (merchant of record). VAT/GST included where
          required.
        </p>
      </section>
    </main>
  );
}
