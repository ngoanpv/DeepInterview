import * as React from "react";
import { cn } from "@/lib/cn";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, rows = 5, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        rows={rows}
        className={cn(
          "w-full rounded-[10px] border border-line bg-panel px-3.5 py-2.5",
          "text-[14.5px] leading-relaxed text-ink placeholder:text-faint resize-y",
          "transition-colors focus:border-accent focus:outline-none",
          "focus-visible:ring-2 focus-visible:ring-accent-soft",
          "disabled:opacity-50 disabled:pointer-events-none",
          className,
        )}
        {...props}
      />
    );
  },
);
Textarea.displayName = "Textarea";
