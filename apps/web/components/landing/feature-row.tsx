import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Reveal } from "@/components/ui/reveal";
import { cn } from "@/lib/cn";

interface FeatureRowProps {
  eyebrow: string;
  title: string;
  body: string;
  bullets: string[];
  visual: ReactNode;
  flip?: boolean;
  first?: boolean;
}

export function FeatureRow({
  eyebrow,
  title,
  body,
  bullets,
  visual,
  flip,
  first,
}: FeatureRowProps) {
  return (
    <Reveal>
      <div
        className={cn(
          "grid items-center gap-[54px] border-t border-line py-[46px] md:grid-cols-2",
          first && "border-t-0",
        )}
      >
        <div className={cn(flip && "md:order-2")}>
          <Eyebrow className="mb-3.5 block">{eyebrow}</Eyebrow>
          <h3 className="serif mb-3.5 text-[27px]">{title}</h3>
          <p className="mb-4 text-[15.5px] text-ink-soft">{body}</p>
          <ul className="flex flex-col gap-2.5">
            {bullets.map((b) => (
              <li key={b} className="flex gap-2.5 text-[14.5px] text-ink-soft">
                <Check
                  size={17}
                  className="mt-[3px] flex-shrink-0 text-accent"
                />
                {b}
              </li>
            ))}
          </ul>
        </div>
        <div
          className={cn(
            "rounded-[14px] border border-line bg-panel p-[22px] shadow-[0_18px_40px_-30px_rgba(20,20,30,0.25)]",
            flip && "md:order-1",
          )}
        >
          {visual}
        </div>
      </div>
    </Reveal>
  );
}
