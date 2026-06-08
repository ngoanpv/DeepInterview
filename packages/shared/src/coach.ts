import { z } from "zod";
import { LanguageSchema } from "./primitives";
import { CitationSchema } from "./company";

// Mastery state for a study module (matches the web StudyModule union in
// apps/web/lib/sample-mastery.ts). Distinct from MasteryLevel (scoring bands).
export const MasteryStateSchema = z.enum([
  "unseen",
  "learning",
  "shaky",
  "mastered",
]);
export type MasteryState = z.infer<typeof MasteryStateSchema>;

// One ordered step in the gap -> study path, built from a weak competency.
export const StudyModuleSchema = z.object({
  id: z.string(),
  title: z.string(),
  competency: z.string(),
  status: MasteryStateSchema,
  est_min: z.number().int(),
  rationale: z.string(),
});
export type StudyModule = z.infer<typeof StudyModuleSchema>;

// The Study Coach's curriculum, derived from a scorecard's weak_competencies.
export const StudyPlanSchema = z.object({
  modules: z.array(StudyModuleSchema),
  summary: z.string(),
  total_min: z.number().int(),
});
export type StudyPlan = z.infer<typeof StudyPlanSchema>;

// A learner's question to the coach chat.
export const CoachChatRequestSchema = z.object({
  session_id: z.string(),
  query: z.string(),
  lang: LanguageSchema,
});
export type CoachChatRequest = z.infer<typeof CoachChatRequestSchema>;

// A grounded, synthesized coaching answer with sources and suggested follow-ups.
export const CoachReplySchema = z.object({
  answer: z.string(),
  citations: z.array(CitationSchema),
  follow_ups: z.array(z.string()),
});
export type CoachReply = z.infer<typeof CoachReplySchema>;
