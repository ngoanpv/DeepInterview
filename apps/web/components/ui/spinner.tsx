import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

export interface SpinnerProps {
  className?: string;
  /** Accessible label announced to screen readers. */
  label?: string;
}

export function Spinner({ className, label = "Loading" }: SpinnerProps) {
  return (
    <span role="status" aria-live="polite" className="inline-flex">
      <Loader2
        aria-hidden="true"
        className={cn("h-4 w-4 animate-spin text-muted", className)}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
