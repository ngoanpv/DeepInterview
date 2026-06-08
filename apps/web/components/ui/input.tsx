import * as React from "react";
import { cn } from "@/lib/cn";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          "w-full rounded-[10px] border border-line bg-panel px-3.5 py-2.5",
          "text-[14.5px] text-ink placeholder:text-faint",
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
Input.displayName = "Input";
