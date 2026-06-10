import { Plus } from "lucide-react";
import { Container } from "@/components/ui/container";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Reveal } from "@/components/ui/reveal";

const ITEMS = [
  {
    q: "Which languages are supported?",
    a: "English is the default, with first-class support for 10+ languages including Vietnamese, Spanish, Hindi, Bahasa, Portuguese and more. Each language is a pluggable pack, so coverage keeps growing — and you can interview for the same role in two languages.",
  },
  {
    q: "Is it really free and open source?",
    a: "Yes. The core is open source under AGPLv3 — self-host it with your own model keys and own your data end to end. Add a language pack or new interviewer persona and contribute it back.",
  },
  {
    q: "What are the avatars?",
    a: "Original, IP-safe video personas — an anime mentor, a hero-mode coach, a professional recruiter — that react to the conversation. They're pre-rendered, so they stay smooth on any device.",
  },
];

export function Faq() {
  return (
    <section id="faq" className="scroll-mt-24 border-t border-line py-[84px]">
      <Container>
        <Reveal className="mb-8 max-w-[680px]">
          <Eyebrow>FAQ</Eyebrow>
          <h2 className="serif mt-3.5 text-[38px]">Good questions.</h2>
        </Reveal>
        {ITEMS.map((item) => (
          <details key={item.q} className="group border-b border-line py-5">
            <summary className="flex cursor-pointer list-none items-center justify-between text-[17px] font-medium [&::-webkit-details-marker]:hidden">
              {item.q}
              <Plus
                size={18}
                className="text-faint transition-transform duration-200 group-open:rotate-45"
              />
            </summary>
            <p className="mt-3 max-w-[760px] text-[15px] text-ink-soft">
              {item.a}
            </p>
          </details>
        ))}
      </Container>
    </section>
  );
}
