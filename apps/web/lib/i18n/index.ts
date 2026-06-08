import { en, type Messages } from "./messages/en";

/** Supported UI locales. English-first; more packs plug in here. */
export type Locale = "en" | "vi";

export const DEFAULT_LOCALE: Locale = "en";

const dictionaries: Record<Locale, Messages> = {
  en,
  // English-only for now; `vi` falls back to `en` until a pack lands.
  vi: en,
};

/** Resolve the message dictionary for a locale (defaults to English). */
export function getMessages(locale: Locale = DEFAULT_LOCALE): Messages {
  return dictionaries[locale] ?? en;
}

/**
 * Read a dot-path key from a messages dictionary, e.g. `t(messages, "nav.setup")`.
 * Returns the key itself if the path is missing (visible-but-safe fallback).
 */
export function t(messages: Messages, key: string): string {
  const value = key
    .split(".")
    .reduce<unknown>(
      (acc, part) =>
        acc && typeof acc === "object"
          ? (acc as Record<string, unknown>)[part]
          : undefined,
      messages,
    );
  return typeof value === "string" ? value : key;
}

export { en };
export type { Messages };
