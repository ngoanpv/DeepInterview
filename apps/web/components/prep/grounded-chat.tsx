"use client";

import { useEffect, useRef, useState } from "react";
import { Send, ExternalLink, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/cn";
import { askCoach, type Citation } from "@/lib/coach";

interface ChatTurn {
  id: string;
  role: "user" | "coach";
  text: string;
  citations?: Citation[];
}

const SUGGESTIONS = [
  "How do I structure a STAR answer?",
  "What does exactly-once mean in Kafka?",
  "How do I show leadership beyond my team?",
];

/**
 * Grounded coach chat. The user asks; we call `queryKnowledge` (which proxies to
 * LightRAG or a mock), then render the answer with citation chips that link out.
 * The thinking state is deliberately "RAG-delay friendly" — it names the phase
 * (retrieving → grounding) so a multi-second retrieval feels intentional, not
 * stalled.
 */
export function GroundedChat() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState<"retrieving" | "grounding">("retrieving");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Cycle the thinking label so a slow retrieval reads as progress.
  useEffect(() => {
    if (!loading) return;
    setPhase("retrieving");
    const t = setTimeout(() => setPhase("grounding"), 900);
    return () => clearTimeout(t);
  }, [loading]);

  // Keep the latest turn in view.
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns, loading]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || loading) return;

    const userTurn: ChatTurn = {
      id: `u-${Date.now()}`,
      role: "user",
      text: q,
    };
    setTurns((prev) => [...prev, userTurn]);
    setInput("");
    setLoading(true);

    try {
      const res = await askCoach(q, "en");
      setTurns((prev) => [
        ...prev,
        {
          id: `c-${Date.now()}`,
          role: "coach",
          text: res.answer,
          citations: res.citations,
        },
      ]);
    } catch {
      setTurns((prev) => [
        ...prev,
        {
          id: `c-${Date.now()}`,
          role: "coach",
          text: "I couldn't reach the knowledge base just now. Try again in a moment.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-line px-6 py-4">
        <div>
          <Eyebrow>AI study coach</Eyebrow>
          <h3 className="mt-1 font-serif text-lg text-ink">Ask your coach</h3>
        </div>
        <Sparkles className="h-4 w-4 text-accent" aria-hidden />
      </div>

      <div
        ref={scrollRef}
        className="flex-1 space-y-4 overflow-y-auto px-6 py-5"
        style={{ minHeight: 280, maxHeight: 460 }}
      >
        {turns.length === 0 && !loading && (
          <div className="text-[14px] leading-relaxed text-muted">
            <p>
              Ask anything about your weak areas. Your coach explains concepts
              and gives worked examples; when grounded sources are available,
              they appear with each answer.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => ask(s)}
                  className="rounded-full border border-line px-3 py-1.5 text-[12.5px] text-ink-soft transition-colors hover:border-ink hover:bg-panel"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t) => (
          <div
            key={t.id}
            className={cn(
              "flex",
              t.role === "user" ? "justify-end" : "justify-start",
            )}
          >
            <div
              className={cn(
                "max-w-[88%] rounded-card px-4 py-3 text-[14px] leading-relaxed",
                t.role === "user"
                  ? "bg-ink text-white"
                  : "border border-line bg-paper text-ink-soft",
              )}
            >
              <p className="whitespace-pre-wrap">{t.text}</p>

              {t.citations && t.citations.length > 0 && (
                <div className="mt-3 border-t border-line pt-3">
                  <p className="mb-2 font-mono text-[10.5px] uppercase tracking-[0.12em] text-faint">
                    Sources
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {t.citations.map((c, i) => (
                      <a
                        key={`${t.id}-cite-${i}`}
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group inline-flex items-start gap-1.5 rounded-md border border-line bg-panel px-2.5 py-1.5 text-[12.5px] text-ink-soft no-underline transition-colors hover:border-accent hover:text-accent"
                        title={c.snippet ?? undefined}
                      >
                        <ExternalLink
                          className="mt-0.5 h-3 w-3 shrink-0 text-faint group-hover:text-accent"
                          aria-hidden
                        />
                        <span className="min-w-0">
                          <span className="block font-medium">{c.title}</span>
                          {c.snippet && (
                            <span className="mt-0.5 block text-[11.5px] text-muted">
                              {c.snippet}
                            </span>
                          )}
                        </span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="inline-flex items-center gap-2.5 rounded-card border border-line bg-paper px-4 py-3 text-[13px] text-muted">
              <Spinner label="Thinking" />
              <span>
                {phase === "retrieving"
                  ? "Retrieving from your knowledge base…"
                  : "Grounding the answer in sources…"}
              </span>
            </div>
          </div>
        )}
      </div>

      <CardContent className="border-t border-line py-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about a weak area…"
            aria-label="Ask the coach a question"
            disabled={loading}
            className="flex-1 rounded-[10px] border border-line bg-panel px-3.5 py-2.5 text-[14px] text-ink placeholder:text-faint focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-paper disabled:opacity-50"
          />
          <Button
            type="submit"
            size="md"
            disabled={loading || input.trim().length === 0}
            aria-label="Send question"
          >
            <Send className="h-4 w-4" aria-hidden />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
