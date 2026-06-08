import * as React from "react";
import { cn } from "@/lib/cn";

export type LabelProps = React.LabelHTMLAttributes<HTMLLabelElement>;

export const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, ...props }, ref) => {
    return (
      <label
        ref={ref}
        className={cn(
          "block text-[13px] font-medium text-ink-soft mb-1.5",
          className,
        )}
        {...props}
      />
    );
  },
);
Label.displayName = "Label";
