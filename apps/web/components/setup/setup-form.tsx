"use client";

import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { UploadCloud, FileText, X } from "lucide-react";
import {
  LANGUAGES,
  type Language,
  type LanguageMode,
} from "@deepinterview/shared";
import { startSession } from "@/app/setup/actions";
import { PERSONAS, DEFAULT_PERSONA_ID } from "@/lib/personas";
import { useMessages } from "@/lib/i18n/client";
import { t } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { DeviceCheck } from "@/components/setup/device-check";

// A small, friendly subset for the picker; full set still lives in LANGUAGES.
const LANGUAGE_LABELS: Partial<Record<Language, string>> = {
  en: "English",
  vi: "Tiếng Việt",
  es: "Español",
  zh: "中文",
  fr: "Français",
  de: "Deutsch",
  ja: "日本語",
};
const OFFERED: Language[] = (
  ["en", "vi", "es", "zh", "fr", "de", "ja"] as Language[]
).filter((l) => (LANGUAGES as readonly string[]).includes(l));

type Step = { key: string; label: string };

// Friendly client-side minimums. The backend is the real guard — these just
// block obviously-empty / garbage-short submits with a helpful nudge.
const MIN_JD_CHARS = 40;
const MIN_CV_CHARS = 30;

// One-click sample inputs for fast testing / demos. Each is a matched CV + JD +
// company so the prep pipeline gets a coherent pair. Pure UX sugar — clicking a
// sample just fills the form fields; nothing is submitted.
const SAMPLES = [
  {
    id: "backend",
    label: "Backend Engineer · Stripe",
    company: "Stripe",
    cv: "Jordan Rivera — Senior Backend Engineer. 7 years building high-throughput payment and API platforms. Led a ledger service at 5k req/s; cut p99 latency 40% with async batching; owned idempotency and reconciliation. Skills: Python, Go, PostgreSQL, Kafka, gRPC, Kubernetes, distributed systems.",
    jd: "Senior Backend Engineer to build payment APIs at scale. Own services in Python/Go, design event-driven systems with Kafka, and ensure reliability, idempotency, and low p99 latency on PostgreSQL. Strong distributed-systems background required.",
  },
  {
    id: "frontend",
    label: "Frontend Engineer · Vercel",
    company: "Vercel",
    cv: "Sam Chen — Senior Frontend Engineer. 6 years shipping performant React/Next.js apps. Built a design system used across 30+ surfaces; improved LCP 35% with streaming SSR and image optimization. Skills: TypeScript, React, Next.js, Tailwind, accessibility, Core Web Vitals.",
    jd: "Senior Frontend Engineer to build fast, delightful web experiences with Next.js and React. Own component architecture, Core Web Vitals, accessibility, and design-system work. Deep TypeScript and modern rendering (SSR/streaming) experience expected.",
  },
  {
    id: "ml",
    label: "ML Engineer · OpenAI",
    company: "OpenAI",
    cv: "Priya Nair — Machine Learning Engineer. 5 years in production ML: built feature pipelines and model serving for ranking at scale; owned offline/online evaluation and safe rollback. Skills: Python, PyTorch, Ray, feature stores, evaluation, MLOps, monitoring.",
    jd: "Machine Learning Engineer to build and ship production ML systems: data pipelines, training, evaluation, and low-latency serving. You will own offline/online metrics, monitoring, and safe rollouts. Strong Python + PyTorch and MLOps experience required.",
  },
] as const;

export function SetupForm({ r2Configured }: { r2Configured: boolean }) {
  const router = useRouter();
  const messages = useMessages();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [cvText, setCvText] = useState("");
  const [jdText, setJdText] = useState("");
  const [company, setCompany] = useState("");
  const [primary, setPrimary] = useState<Language>("en");
  const [mixed, setMixed] = useState(false);
  const [personaId, setPersonaId] = useState(DEFAULT_PERSONA_ID);

  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Surface inline field errors once the user has interacted with a field (or
  // attempted submit) — not on first load. Decoupled from submit because the
  // submit button is disabled while invalid, so it never fires onSubmit.
  const [cvTouched, setCvTouched] = useState(false);
  const [jdTouched, setJdTouched] = useState(false);

  // --- Client-side input validation (friendly; backend is the real guard) ---
  // CV is satisfied by a chosen file (length unknown synchronously) OR pasted
  // text of at least MIN_CV_CHARS. JD must be present + reasonably long.
  // Company is optional.
  const cvLen = cvText.trim().length;
  const jdLen = jdText.trim().length;
  const cvError = !file
    ? cvLen === 0
      ? t(messages, "setup.needCv")
      : cvLen < MIN_CV_CHARS
        ? `Add a bit more — your CV text looks too short (at least ${MIN_CV_CHARS} characters).`
        : null
    : null;
  const jdError =
    jdLen === 0
      ? t(messages, "setup.needJd")
      : jdLen < MIN_JD_CHARS
        ? `Paste the full posting — this looks too short (at least ${MIN_JD_CHARS} characters).`
        : null;
  const canSubmit = !cvError && !jdError && !submitting;

  // Fill the form with a matched sample (testing / demo). Clears any chosen file
  // so the pasted sample CV text is what gets submitted.
  function loadSample(s: (typeof SAMPLES)[number]) {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setCvText(s.cv);
    setJdText(s.jd);
    setCompany(s.company);
    setCvTouched(false);
    setJdTouched(false);
    setError(null);
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }, []);

  /**
   * Read a file as a base64 `data:` URL of its RAW bytes (no R2 configured).
   * The agent base64-decodes this and parses the real document (PDF/DOCX) —
   * unlike `file.text()`, which mangles binary formats into garbage.
   */
  function fileToDataUrl(f: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () =>
        reject(reader.error ?? new Error("Could not read file."));
      reader.readAsDataURL(f);
    });
  }

  /** Upload the chosen file to R2 (presign → PUT) and return its public URL. */
  async function uploadToR2(f: File): Promise<string> {
    const res = await fetch("/api/upload", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        filename: f.name,
        content_type: f.type || "application/octet-stream",
      }),
    });
    if (!res.ok) throw new Error("Upload could not be prepared.");
    const { uploadUrl, publicUrl } = (await res.json()) as {
      uploadUrl: string;
      publicUrl: string;
    };
    const put = await fetch(uploadUrl, {
      method: "PUT",
      headers: { "content-type": f.type || "application/octet-stream" },
      body: f,
    });
    if (!put.ok) throw new Error("File upload failed.");
    return publicUrl;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    // Client-side validation. CV can be a file OR pasted text; JD required +
    // min length; company is optional. Surface inline field errors and bail.
    if (cvError || jdError) {
      setCvTouched(true);
      setJdTouched(true);
      return;
    }

    setSubmitting(true);
    setActiveStep(0);

    try {
      // CV resolution: upload only when a file is chosen AND R2 is configured.
      // Otherwise pass the pasted text directly as cv_url — the prep pipeline
      // treats a non-URL cv_url as the document itself (offline-friendly).
      let cv_url: string;
      if (file && r2Configured) {
        cv_url = await uploadToR2(file);
      } else if (cvText.trim()) {
        cv_url = cvText.trim();
      } else if (file) {
        // File chosen but no storage — send the RAW bytes as a base64 data URL
        // so the agent can parse the real document (NOT file.text(), which
        // turns a PDF/DOCX into binary garbage).
        cv_url = await fileToDataUrl(file);
      } else {
        cv_url = "";
      }

      setActiveStep(1);
      const language_mode: LanguageMode = { primary, mixed };
      const result = await startSession({
        cv_url,
        jd_text: jdText.trim(),
        company: company.trim(),
        language_mode,
      });

      if (!result.ok) {
        // Out of interviews → send the user to pricing to upgrade / buy credits.
        if (result.reason === "out_of_interviews") {
          router.push("/pricing");
          return;
        }
        setError(result.error);
        setSubmitting(false);
        return;
      }

      setActiveStep(2);
      // Carry the chosen persona forward (PrepRequest has no persona field yet;
      // WP-2 will persist it server-side). Query param keeps P1 stateless.
      // Route to the prep screen — it polls the agent, shows the agents
      // working, then the "what we found" bento, then hands off to /interview.
      router.push(
        `/session/${result.session_id}${
          personaId ? `?persona=${encodeURIComponent(personaId)}` : ""
        }`,
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t(messages, "common.error"),
      );
      setSubmitting(false);
    }
  }

  const steps: Step[] = [
    { key: "cv", label: t(messages, "setup.stepCv") },
    { key: "company", label: t(messages, "setup.stepCompany") },
    { key: "plan", label: t(messages, "setup.stepPlan") },
  ];

  if (submitting) {
    const researching = t(messages, "setup.researching").replace(
      "{company}",
      company.trim() || "the company",
    );
    return (
      <Card className="mt-8">
        <CardContent className="flex flex-col items-center gap-5 py-12 text-center">
          <Spinner className="h-6 w-6" />
          <p className="serif text-xl text-ink">{researching}</p>
          <ol className="flex flex-col gap-2 text-left">
            {steps.map((s, i) => (
              <li
                key={s.key}
                className={cn(
                  "flex items-center gap-2 text-[13px]",
                  i < activeStep
                    ? "text-ok"
                    : i === activeStep
                      ? "text-ink"
                      : "text-faint",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    i < activeStep
                      ? "bg-ok"
                      : i === activeStep
                        ? "bg-accent"
                        : "bg-line",
                  )}
                />
                {s.label}
              </li>
            ))}
          </ol>
          {error && (
            <p className="text-[13px] text-ink-soft" role="alert">
              {error}
            </p>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-6">
      <div>
        <h1 className="serif text-3xl text-ink">
          {t(messages, "setup.title")}
        </h1>
        <p className="mt-2 text-ink-soft">{t(messages, "setup.subtitle")}</p>
      </div>

      {/* Quick demo: one-click sample CV + JD + company for fast testing */}
      <Card className="border-dashed">
        <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[13px] font-medium text-ink">Quick demo</p>
            <p className="text-[12px] text-muted">
              Load a matched sample CV + job description to try it fast.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {SAMPLES.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => loadSample(s)}
                className="rounded-[10px] border border-line px-3 py-1.5 text-[12px] text-ink-soft transition-colors hover:border-ink"
              >
                {s.label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* CV */}
      <Card>
        <CardHeader>
          <CardTitle>{t(messages, "setup.cvLabel")}</CardTitle>
          <CardDescription>{t(messages, "setup.cvHint")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 pb-6">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "flex cursor-pointer flex-col items-center gap-2 rounded-[10px] border border-dashed px-4 py-8 text-center transition-colors",
              dragging
                ? "border-accent bg-accent-soft"
                : "border-line hover:border-ink",
            )}
          >
            {file ? (
              <span className="flex items-center gap-2 text-[14px] text-ink">
                <FileText className="h-4 w-4 text-accent" aria-hidden />
                {file.name}
                <button
                  type="button"
                  aria-label="Remove file"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                  className="text-muted hover:text-ink"
                >
                  <X className="h-4 w-4" />
                </button>
              </span>
            ) : (
              <>
                <UploadCloud className="h-5 w-5 text-muted" aria-hidden />
                <span className="text-[13px] text-muted">
                  {t(messages, "setup.cvDrop")}
                </span>
              </>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <div>
            <Label htmlFor="cvText">{t(messages, "setup.cvPasteLabel")}</Label>
            <Textarea
              id="cvText"
              rows={5}
              placeholder={t(messages, "setup.cvPasteHint")}
              value={cvText}
              onChange={(e) => setCvText(e.target.value)}
              onBlur={() => setCvTouched(true)}
              aria-invalid={cvTouched && Boolean(cvError)}
            />
          </div>
          {cvTouched && cvError && (
            <p className="text-[13px] text-accent" role="alert">
              {cvError}
            </p>
          )}
        </CardContent>
      </Card>

      {/* JD */}
      <Card>
        <CardHeader>
          <CardTitle>{t(messages, "setup.jdLabel")}</CardTitle>
          <CardDescription>{t(messages, "setup.jdHint")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 pb-6">
          <Textarea
            rows={6}
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            onBlur={() => setJdTouched(true)}
            aria-label={t(messages, "setup.jdLabel")}
            aria-invalid={jdTouched && Boolean(jdError)}
          />
          {jdTouched && jdError && (
            <p className="text-[13px] text-accent" role="alert">
              {jdError}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Company */}
      <Card>
        <CardHeader>
          <CardTitle>{t(messages, "setup.companyLabel")}</CardTitle>
          <CardDescription>{t(messages, "setup.companyHint")}</CardDescription>
        </CardHeader>
        <CardContent className="pb-6">
          <Input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Stripe (optional)"
            aria-label={t(messages, "setup.companyLabel")}
          />
        </CardContent>
      </Card>

      {/* Language mode */}
      <Card>
        <CardHeader>
          <CardTitle>{t(messages, "setup.languageLabel")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 pb-6">
          <div className="flex flex-wrap gap-2">
            {OFFERED.map((lang) => (
              <button
                key={lang}
                type="button"
                onClick={() => setPrimary(lang)}
                aria-pressed={primary === lang}
                className={cn(
                  "rounded-[10px] border px-3.5 py-2 text-[13px] transition-colors",
                  primary === lang
                    ? "border-accent bg-accent-soft text-accent"
                    : "border-line text-ink-soft hover:border-ink",
                )}
              >
                {LANGUAGE_LABELS[lang] ?? lang}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-[13px] text-ink-soft">
            <input
              type="checkbox"
              checked={mixed}
              onChange={(e) => setMixed(e.target.checked)}
              className="h-4 w-4 accent-[var(--color-accent)]"
            />
            {t(messages, "setup.languageMixed")}
          </label>
        </CardContent>
      </Card>

      {/* Persona */}
      <Card>
        <CardHeader>
          <CardTitle>{t(messages, "setup.personaLabel")}</CardTitle>
          <CardDescription>{t(messages, "setup.personaHint")}</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 pb-6 sm:grid-cols-3">
          {PERSONAS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPersonaId(p.id)}
              aria-pressed={personaId === p.id}
              className={cn(
                "flex flex-col gap-2 rounded-[10px] border p-3 text-left transition-colors",
                personaId === p.id
                  ? "border-accent bg-accent-soft"
                  : "border-line hover:border-ink",
              )}
            >
              <div
                className="aspect-[4/3] w-full rounded-md border border-line bg-paper bg-cover bg-center"
                style={{ backgroundImage: `url(${p.poster_url})` }}
                aria-hidden
              />
              <div>
                <p className="text-[14px] font-medium text-ink">{p.name}</p>
                <p className="text-[12px] leading-snug text-muted">{p.style}</p>
              </div>
            </button>
          ))}
        </CardContent>
      </Card>

      {/* Device check */}
      <Card>
        <CardHeader>
          <CardTitle>{t(messages, "setup.deviceLabel")}</CardTitle>
        </CardHeader>
        <CardContent className="pb-6">
          <DeviceCheck />
        </CardContent>
      </Card>

      {error && (
        <p className="text-[13px] text-ink-soft" role="alert">
          {error}
        </p>
      )}

      <Button
        type="submit"
        size="lg"
        className="self-start"
        disabled={!canSubmit}
        aria-disabled={!canSubmit}
      >
        {t(messages, "setup.start")}
      </Button>
    </form>
  );
}
