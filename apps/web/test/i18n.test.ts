import { describe, expect, it } from "vitest";
import { en } from "../lib/i18n/messages/en";
import { vi } from "../lib/i18n/messages/vi";
import { DEFAULT_LOCALE, getMessages, t } from "../lib/i18n";

/** Every string leaf path in `en`, e.g. ["nav.setup", "interview.end", ...]. */
function leafPaths(obj: unknown, prefix = ""): string[] {
  if (typeof obj === "string") return [prefix];
  if (obj && typeof obj === "object") {
    return Object.entries(obj).flatMap(([k, v]) =>
      leafPaths(v, prefix ? `${prefix}.${k}` : k),
    );
  }
  return [];
}

describe("Vietnamese UI pack (issue #50)", () => {
  it("resolves `vi` to the real dictionary, not English", () => {
    expect(DEFAULT_LOCALE).toBe("en");
    expect(getMessages("vi")).toBe(vi);
    expect(getMessages("en")).toBe(en);
    // Spot-check: the pack is actually translated.
    expect(t(getMessages("vi"), "setup.start")).toBe("Bắt đầu phỏng vấn");
    expect(t(getMessages("vi"), "setup.start")).not.toBe(
      t(getMessages("en"), "setup.start"),
    );
  });

  it("covers every `en` key (parity is also enforced by tsc)", () => {
    const missing = leafPaths(en).filter((p) => t(vi, p) === p);
    expect(missing).toEqual([]);
  });

  it("falls back visibly for unknown keys", () => {
    expect(t(getMessages("vi"), "no.such.key")).toBe("no.such.key");
    expect(t(getMessages("en"), "no.such.key")).toBe("no.such.key");
  });
});
