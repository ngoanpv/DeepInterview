import Link from "next/link";
import { features } from "@deepinterview/ee";
import { Container } from "@/components/ui/container";
import { buttonClasses } from "@/components/ui/button";
import { MobileMenu } from "@/components/landing/mobile-menu";
import { GITHUB_URL } from "@/lib/site";

export const NAV_LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#product", label: "Product" },
  { href: "#oss", label: "Open source" },
  { href: "#faq", label: "FAQ" },
];

export function Nav() {
  return (
    <nav className="sticky top-0 z-50 border-b border-line bg-paper/80 backdrop-blur-md">
      <Container className="flex h-[66px] items-center justify-between">
        <a href="#top" className="flex items-center gap-[9px]">
          <span className="grid h-[22px] w-[22px] place-items-center rounded-md border-[1.5px] border-ink font-serif text-sm leading-none">
            D
          </span>
          <span className="text-[17px] font-semibold tracking-[-0.01em]">
            DeepInterview
          </span>
        </a>

        <div className="hidden gap-[30px] text-[14.5px] text-ink-soft min-[861px]:flex">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="hover:text-ink">
              {link.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-3.5">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="hidden text-[14.5px] text-ink-soft hover:text-ink min-[861px]:inline"
          >
            GitHub
          </a>
          {features.auth ? (
            <Link
              href="/login"
              className="hidden text-[14.5px] text-ink-soft hover:text-ink min-[861px]:inline"
            >
              Sign in
            </Link>
          ) : null}
          <Link href="/setup" className={buttonClasses()}>
            Start free
          </Link>
          <MobileMenu
            links={
              features.auth
                ? [...NAV_LINKS, { href: "/login", label: "Sign in" }]
                : NAV_LINKS
            }
          />
        </div>
      </Container>
    </nav>
  );
}
