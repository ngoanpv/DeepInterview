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

/** Input to {@link gateRequest}: one request's identity-relevant facts. */
export interface GateInput {
  /** Request pathname, e.g. "/setup" or "/api/upload". */
  readonly pathname: string;
  /** Whether the request carries a signed-in user. */
  readonly isAuthenticated: boolean;
}

export type GateResult =
  | { readonly allow: true }
  | { readonly allow: false; readonly redirectTo?: string };

/**
 * Access decision for a request. Consumers:
 * - the web proxy (page navigations) redirects to `redirectTo` on deny;
 * - cost-bearing route handlers (/api/upload, /api/coach/chat, /api/kb/query)
 *   respond 401 on deny and ignore `redirectTo`.
 *
 * The OSS build allows everything (auth stays optional / self-host friendly).
 * A distribution that flips `features.auth` decides here which paths require
 * a signed-in user.
 */
export function gateRequest(_input: GateInput): GateResult {
  return { allow: true };
}
