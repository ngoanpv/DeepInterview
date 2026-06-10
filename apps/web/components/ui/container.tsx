import * as React from "react";
import { cn } from "@/lib/cn";

/** Editorial page gutter — mirrors the reference `.wrap` (max 1140px, 28px sides). */
export function Container({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("mx-auto w-full max-w-[1140px] px-7", className)}
      {...props}
    />
  );
}
