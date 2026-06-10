import { Container } from "@/components/ui/container";
import { GITHUB_URL } from "@/lib/site";

export function AnnouncementBar() {
  return (
    <div className="border-b border-line bg-panel">
      <Container className="flex h-[38px] items-center justify-center gap-2.5 text-[13px] text-muted">
        <span
          aria-hidden="true"
          className="inline-block h-[5px] w-[5px] rounded-full bg-accent"
        />
        <b className="font-semibold text-ink">
          Open source &amp; self-hostable
        </b>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noreferrer"
          className="text-muted hover:text-ink"
        >
          ★ Star us on GitHub →
        </a>
      </Container>
    </div>
  );
}
