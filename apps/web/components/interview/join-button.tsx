"use client";

import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

type State = "idle" | "joining" | "connected" | "error";

/**
 * Requests a LiveKit token for this session. On success shows a placeholder
 * "connected" state — the full orb/avatar/transcript screen is WP-2. Gated:
 * fires only on click, and tolerates a 501 (LiveKit unconfigured) gracefully.
 */
export function JoinButton({ sessionId }: { sessionId: string }) {
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function join() {
    setState("joining");
    setMessage(null);
    try {
      const res = await fetch("/api/token", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
          error?: string;
        };
        setMessage(body.error ?? `Could not join (${res.status}).`);
        setState("error");
        return;
      }
      setState("connected");
    } catch {
      setMessage("Could not reach the interview service.");
      setState("error");
    }
  }

  if (state === "connected") {
    return (
      <div className="flex items-center gap-2 rounded-[10px] border border-line bg-accent-soft px-3.5 py-3 text-[13px] text-ink-soft">
        <CheckCircle2 className="h-4 w-4 text-ok" aria-hidden />
        Connected — live interview UI lands in WP-2.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        size="lg"
        onClick={join}
        disabled={state === "joining"}
        className="self-start"
      >
        {state === "joining" && <Spinner className="text-white" />}
        Join interview
      </Button>
      {state === "error" && message && (
        <p className="text-[13px] text-ink-soft" role="alert">
          {message}
        </p>
      )}
    </div>
  );
}
