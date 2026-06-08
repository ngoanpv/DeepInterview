import * as React from "react";
import { cn } from "@/lib/cn";

export type EyebrowProps = React.HTMLAttributes<HTMLParagraphElement>;

/** Mono, uppercase, tracked accent label used above headings (editorial). */
export function Eyebrow({ className, ...props }: EyebrowProps) {
  return (
    <p
      className={cn(
        "font-mono text-xs uppercase tracking-[0.14em] text-accent",
        className,
      )}
      {...props}
    />
  );
}
