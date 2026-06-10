import Link from "next/link";
import { Check, ArrowUpRight } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Reveal } from "@/components/ui/reveal";
import { buttonClasses } from "@/components/ui/button";
import { HeroMock } from "@/components/landing/hero-mock";
import { GITHUB_URL } from "@/lib/site";

export function Hero() {
  return (
    <header id="top" className="border-b border-line">
      <Container className="grid items-center gap-11 pt-[84px] pb-16 min-[920px]:grid-cols-[1.04fr_0.96fr] min-[920px]:gap-14">
        <div>
          <Eyebrow>Open-source AI interviewer</Eyebrow>
          <h1 className="serif mt-[18px] mb-[22px] text-[44px] text-ink min-[920px]:text-[60px]">
            Practice the interview{" "}
            <em className="italic text-accent">out loud.</em>
            <br />
            Then pass the real one.
          </h1>
          <p className="mb-7 max-w-[520px] text-lg text-ink-soft">
            DeepInterview reads your CV and the job description, researches the
            company, and runs a real voice mock interview — then shows you
            exactly what to fix. English-first, available in 10+ languages.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link href="/setup" className={buttonClasses()}>
              Start free
            </Link>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              className={buttonClasses({ variant: "out" })}
            >
              View on GitHub <ArrowUpRight size={16} />
            </a>
          </div>
          <div className="mt-[18px] flex flex-wrap gap-3.5 text-[13px] text-faint">
            <span className="flex items-center gap-1.5">
              <Check size={14} className="text-ok" /> No credit card
            </span>
            <span className="flex items-center gap-1.5">
              <Check size={14} className="text-ok" /> Self-host with your own
              keys
            </span>
            <span className="flex items-center gap-1.5">
              <Check size={14} className="text-ok" /> Apache 2.0
            </span>
          </div>
        </div>

        <Reveal>
          <HeroMock />
        </Reveal>
      </Container>
    </header>
  );
}
