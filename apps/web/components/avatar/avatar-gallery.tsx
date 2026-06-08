"use client";

/**
 * Client island for the /avatars preview page (WP-9).
 *
 * Renders all personas as <AvatarStage> cards in a grid with a shared state
 * toggle, so the idle ⇄ speaking crossfade and the speaking pulse are visible
 * offline (no assets, no env keys). Pure props in — no LiveKit, no server-only.
 */

import * as React from "react";
import { PERSONAS } from "@/lib/personas";
import { cn } from "@/lib/cn";
import {
  AvatarStage,
  type AvatarState,
} from "@/components/avatar/avatar-stage";

const STATES: AvatarState[] = ["idle", "listening", "thinking", "speaking"];

const STATE_HINT: Record<AvatarState, string> = {
  idle: "Resting between turns — gentle breathing loop.",
  listening: "You're talking — still on the idle loop, attentive.",
  thinking: "Composing a follow-up — idle loop holds.",
  speaking: "Asking a question — crossfades to the speaking loop.",
};

export function AvatarGallery() {
  const [state, setState] = React.useState<AvatarState>("idle");

  return (
    <div className="flex flex-col gap-8">
      {/* State toggle — drives every card at once. */}
      <div className="flex flex-col gap-3">
        <div
          className="inline-flex flex-wrap gap-1 self-start rounded-card border border-line bg-panel p-1"
          role="group"
          aria-label="Avatar state"
        >
          {STATES.map((s) => {
            const active = s === state;
            return (
              <button
                key={s}
                type="button"
                aria-pressed={active}
                onClick={() => setState(s)}
                className={cn(
                  "rounded-[10px] px-4 py-2 font-mono text-xs uppercase tracking-[0.12em]",
                  "transition-colors duration-150 cursor-pointer",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
                  active
                    ? "bg-ink text-white"
                    : "text-muted hover:text-ink hover:bg-accent-soft",
                )}
              >
                {s}
              </button>
            );
          })}
        </div>
        <p className="text-sm text-muted">{STATE_HINT[state]}</p>
      </div>

      {/* Persona grid. */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {PERSONAS.map((persona) => (
          <figure key={persona.id} className="flex flex-col gap-3">
            <AvatarStage persona={persona} state={state} />
            <figcaption className="flex flex-col gap-0.5 px-1">
              <span className="serif text-lg text-ink">{persona.name}</span>
              <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-faint">
                {persona.id}
              </span>
              <span className="mt-1 text-sm leading-snug text-muted">
                {persona.style}
              </span>
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}
