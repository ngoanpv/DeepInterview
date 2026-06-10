import Link from "next/link";
import { Container } from "@/components/ui/container";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Reveal } from "@/components/ui/reveal";
import { buttonClasses } from "@/components/ui/button";
import { GITHUB_URL } from "@/lib/site";

export function CtaBand() {
  return (
    <section className="pb-[84px]">
      <Container>
        <Reveal>
          <div className="rounded-[18px] border border-line bg-panel p-[54px] text-center">
            <Eyebrow>Ready when you are</Eyebrow>
            <h2 className="serif mt-3 mb-3.5 text-[38px]">
              Your next interview starts here.
            </h2>
            <p className="mb-[26px] text-[17px] text-ink-soft">
              Upload a CV, paste a job post, and talk it through — in minutes.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <Link href="/setup" className={buttonClasses()}>
                Start free
              </Link>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noreferrer"
                className={buttonClasses({ variant: "out" })}
              >
                View on GitHub
              </a>
            </div>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
