/**
 * @deepinterview/ee — DeepInterview's open-core extension seam.
 *
 * This OSS stub ships inert defaults under Apache-2.0. A downstream
 * distribution (e.g. a hosted/commercial edition) replaces the CONTENTS of
 * `packages/ee` in its own repo — same package name, same exported surface —
 * and pnpm workspace resolution serves that implementation to every importer.
 * No conditional imports, no build flags, no OSS file edits.
 *
 * Rules for evolving this seam (upstream-first):
 * 1. Hook points are added HERE, in the OSS repo, with inert defaults.
 * 2. OSS code may import this package unconditionally and must behave
 *    identically with the defaults (`features.*` all false).
 * 3. Real (non-default) functionality never lands in this stub.
 */

/** Switches a distribution can enable. All false in the OSS build. */
export interface EeFeatures {
  /** Hosted accounts / SSO. The OSS build runs auth-free. */
  readonly auth: boolean;
  /** Premium voice catalogue beyond the bundled OSS voice packs. */
  readonly premiumVoices: boolean;
  /** Billing and plan gating. */
  readonly billing: boolean;
}

export type Edition = "oss" | "cloud";

/** Which distribution this build is. */
export const edition: Edition = "oss";

export const features: EeFeatures = Object.freeze({
  auth: false,
  premiumVoices: false,
  billing: false,
});
