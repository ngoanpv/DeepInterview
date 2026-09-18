import { en, type Messages } from "./messages/en";
import { vi, type Localized } from "./messages/vi";

/** Supported UI locales. English-first; more packs plug in here. */
export type Locale = "en" | "vi";

export const DEFAULT_LOCALE: Locale = "en";

/**
 * What message readers (`t()`, `useMessages()`) actually handle: the exact
 * `en` key structure with widened string values, so every locale pack fits.
 * `en`'s literals stay the parity anchor (`Messages`); packs are checked
 * against it at compile time in their own files.
 */
export type Dictionary = Localized<Messages>;

const dictionaries: Record<Locale, Dictionary> = {
  en,
  vi,
};

/** Resolve the message dictionary for a locale (defaults to English). */
export function getMessages(locale: Locale = DEFAULT_LOCALE): Dictionary {
  return dictionaries[locale] ?? en;
}

/**
 * Read a dot-path key from a messages dictionary, e.g. `t(messages, "nav.setup")`.
 * Returns the key itself if the path is missing (visible-but-safe fallback).
 */
export function t(messages: Dictionary, key: string): string {
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
