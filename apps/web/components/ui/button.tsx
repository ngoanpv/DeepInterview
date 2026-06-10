import * as React from "react";
import { cn } from "@/lib/cn";

type Variant = "ink" | "out" | "ghost";
type Size = "sm" | "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-2 font-medium rounded-[10px] " +
  "transition-colors duration-150 cursor-pointer select-none " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-paper " +
  "disabled:opacity-50 disabled:pointer-events-none";

const variants: Record<Variant, string> = {
  ink: "bg-ink text-white border border-transparent hover:bg-ink-soft",
  out: "bg-transparent text-ink border border-line hover:border-ink hover:bg-panel",
  ghost:
    "bg-transparent text-ink-soft border border-transparent hover:text-ink hover:bg-accent-soft",
};

const sizes: Record<Size, string> = {
  sm: "text-[13px] px-3 py-1.5",
  md: "text-[14.5px] px-[18px] py-[11px]",
  lg: "text-[15px] px-6 py-3",
};

/** Button styles as a class string — for `<a>`/`<Link>` that should look like a Button. */
export function buttonClasses({
  variant = "ink",
  size = "md",
  className,
}: { variant?: Variant; size?: Size; className?: string } = {}) {
  return cn(base, variants[variant], sizes[size], className);
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant = "ink", size = "md", type = "button", ...props },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        type={type}
        className={buttonClasses({ variant, size, className })}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
