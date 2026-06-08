"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type { Locale } from "@/lib/i18n";
import { cn } from "@/lib/cn";

const OPTIONS: { value: Locale; label: string }[] = [
  { value: "en", label: "EN" },
  { value: "vi", label: "VI" },
];

function readLocaleCookie(): Locale {
  if (typeof document === "undefined") return "en";
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith("locale="));
  const value = match?.split("=")[1];
  return value === "vi" ? "vi" : "en";
}

/**
 * Minimal locale switcher. Persists the choice in a `locale` cookie and
 * refreshes so server components re-render in the new language. English-first:
 * unset cookie resolves to EN.
 */
export function LanguageToggle({ className }: { className?: string }) {
  const router = useRouter();
  const [locale, setLocale] = useState<Locale>("en");

  // Read the cookie after mount so SSR markup stays stable (no hydration drift).
  useEffect(() => {
    setLocale(readLocaleCookie());
  }, []);

  const choose = useCallback(
    (next: Locale) => {
      if (next === locale) return;
      document.cookie = `locale=${next}; path=/; max-age=31536000; samesite=lax`;
      setLocale(next);
      router.refresh();
    },
    [locale, router],
  );

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-[10px] border border-line bg-panel p-0.5",
        className,
      )}
      role="group"
      aria-label="Language"
    >
      {OPTIONS.map((opt) => {
        const active = opt.value === locale;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => choose(opt.value)}
            aria-pressed={active}
            className={cn(
              "rounded-md px-2.5 py-1 font-mono text-[11px] font-medium transition-colors",
              active
                ? "bg-accent-soft text-accent"
                : "text-muted hover:text-ink",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
