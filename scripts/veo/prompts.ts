/**
 * IP-safe Veo 3.1 prompts for the DeepInterview avatar library (handoff §8.1).
 *
 * One-time render workflow (see ./README.md and ./render.mjs):
 *   1. Generate ONE reference still per character from `reference`.
 *   2. Reuse that still as the first frame for BOTH the `idle` and `speaking`
 *      loops, so the two loops match exactly (same outfit/hair/lighting/bg).
 *   3. Render 8s clips with first-frame = last-frame for seamless looping.
 *
 * Framing for every character: medium close-up / talking-head, eyeline to
 * camera; neutral or gradient background for easy compositing; identical
 * lighting across the two loops; audio neutral/none (live TTS overrides it).
 *
 * IP rule (load-bearing): NEVER generate named copyrighted characters — it's
 * infringement for a commercial product AND Veo will refuse/rewrite it. Every
 * prompt below carries:
 *   "original fictional character, not resembling any real person or existing
 *    franchise; no brand logos."
 * (The superhero additionally states it does not resemble Iron Man or any
 * existing franchise hero.)
 *
 * Self-contained on purpose: this file is consumed by the Node render CLI and
 * is NOT part of the web app's tsconfig, so it imports nothing from `@/…`.
 */

/** Mirrors `PersonaId` in apps/web/lib/personas.ts — kept local to avoid an
 * `@/` import that wouldn't resolve outside the web package. */
export type PersonaId = "anime" | "superhero" | "recruiter";

export interface VeoPromptSet {
  /** Prompt for the single reference still (first frame of both loops). */
  reference: string;
  /** Idle / listening / thinking loop: breathing, blink, micro head-sway. */
  idle: string;
  /** Speaking loop: talking mouth, nods, small gestures. */
  speaking: string;
}

/** The shared IP clause appended to every reference prompt. */
const IP_RULE =
  "Original fictional character, not resembling any real person or existing franchise; no brand logos.";

/** Superhero gets an extra, explicit non-IP clause per the handoff — note it
 * still contains the exact base rule substring verbatim. */
const IP_RULE_SUPERHERO =
  "Original fictional character, not resembling Iron Man or any existing franchise hero, and not resembling any real person or existing franchise; no brand logos.";

export const VEO_PROMPTS: Record<PersonaId, VeoPromptSet> = {
  // (a) Anime-style interviewer
  anime: {
    reference: `Medium close-up, anime/cel-shaded style. An original anime-style female interviewer in her twenties, neat dark bob with a hair clip, smart-casual blazer, friendly neutral expression, eyeline to camera. Clean pastel-gradient studio background, soft even anime lighting. Static camera. ${IP_RULE}`,
    idle: `Medium close-up, anime/cel-shaded style. An original anime-style female interviewer in her twenties, neat dark bob with a hair clip, smart-casual blazer, friendly neutral expression. Breathes softly, blinks occasionally, slight head tilt. Clean pastel-gradient studio background, soft even anime lighting. No dialogue, quiet ambient room tone. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE}`,
    speaking: `Same anime-style female interviewer — same outfit, hair, lighting, pastel-gradient background, medium close-up. She speaks warmly and animatedly to camera, natural mouth movement, gentle head nods and small hand gestures, engaged expression. Soft even anime lighting. No specific dialogue audio, neutral ambient tone. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE}`,
  },

  // (b) Superhero-style (original, non-IP)
  superhero: {
    reference: `Medium close-up, cinematic. An original armored superhero in a sleek red-and-gold powered exosuit with a softly glowing chest core and a sculpted helmet (open, confident human face visible), eyeline to camera. Dark neutral studio background, cool-blue rim lighting. Static camera. ${IP_RULE_SUPERHERO}`,
    idle: `Medium close-up, cinematic. An original armored superhero in a sleek red-and-gold powered exosuit with a softly glowing chest core and a sculpted helmet (open, confident human face visible). Subtle breathing, occasional blink, faint pulsing suit glow. Dark neutral studio background, cool-blue rim lighting. Calm and heroic. No dialogue, low ambient hum. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE_SUPERHERO}`,
    speaking: `Same original red-and-gold armored superhero, helmet open, same dark studio background and cool-blue rim lighting, medium close-up. Speaks confidently to camera, natural mouth movement, assured nods and a subtle hand gesture, chest core glowing steadily. Cinematic dramatic lighting. No specific dialogue audio, low ambient hum. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE_SUPERHERO}`,
  },

  // (c) Professional / corporate recruiter
  recruiter: {
    reference: `Medium close-up, photorealistic. A fictional professional male recruiter, late thirties, short tidy hair, light beard, navy blazer over white shirt, warm approachable expression, eyeline to camera, not resembling any real person. Clean light-grey office-studio background with soft bokeh, soft three-point lighting, warm key from left. Static camera. ${IP_RULE}`,
    idle: `Medium close-up, photorealistic. A fictional professional male recruiter, late thirties, short tidy hair, light beard, navy blazer over white shirt, warm approachable expression, not resembling any real person. Subtle breathing, natural blinking, slight head movement. Clean light-grey office-studio background with soft bokeh, soft three-point lighting, warm key from left. No dialogue, quiet office ambience. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE}`,
    speaking: `Same fictional male recruiter — same blazer, hair, background, soft three-point lighting, medium close-up. Speaks in a warm professional manner to camera, natural lip movement, occasional reassuring nods and a small open-hand gesture, attentive expression. No specific dialogue audio, quiet office ambience. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE}`,
  },
};

/** Ordered list of persona ids for CLI iteration. */
export const PERSONA_IDS: PersonaId[] = ["anime", "superhero", "recruiter"];
