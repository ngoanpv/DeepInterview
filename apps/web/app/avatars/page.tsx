import type { Metadata } from "next";
import Link from "next/link";
import { Eyebrow } from "@/components/ui/eyebrow";
import { AvatarGallery } from "@/components/avatar/avatar-gallery";

export const metadata: Metadata = {
  title: "Avatar system · DeepInterview",
  description:
    "Preview the DeepInterview avatar personas and their idle ⇄ speaking states.",
};

/**
 * Offline-viewable proof for WP-9. Server shell (static, no env reads, no
 * server-only imports) wrapping the <AvatarGallery> client island. Renders
 * fully with zero assets via each stage's fallback.
 */
export default function AvatarsPage() {
  return (
    <main className="mx-auto max-w-[1080px] px-6 py-12">
      <header className="flex items-center justify-between">
        <Link href="/" className="no-underline">
          <Eyebrow>DeepInterview</Eyebrow>
        </Link>
      </header>

      <div className="mt-10 flex flex-col gap-3">
        <Eyebrow>Avatar system</Eyebrow>
        <h1 className="serif text-4xl text-ink sm:text-5xl">
          Three personas, two loops, zero cost per minute.
        </h1>
        <p className="max-w-[60ch] text-base leading-relaxed text-muted">
          Each interviewer is a pair of pre-rendered Veo&nbsp;3.1 loops — idle
          and speaking — stacked and crossfaded by the live agent state. No
          real-time avatar SaaS, so runtime cost is just CDN bytes. The stages
          below render their fallback look until the rendered loops are wired
          in; toggle the state to see the crossfade and the speaking pulse.
        </p>
      </div>

      <div className="mt-12">
        <AvatarGallery />
      </div>
    </main>
  );
}
