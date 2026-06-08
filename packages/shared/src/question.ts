import { z } from "zod";
import {
  LanguageModeSchema,
  LocalizedTextSchema,
  SectionSchema,
} from "./primitives";

export const RubricItemSchema = z.object({
  criterion: z.string(),
  weight: z.number(),
  description: z.string(),
});
export type RubricItem = z.infer<typeof RubricItemSchema>;

export const PlannedQuestionSchema = z.object({
  id: z.string(),
  section: SectionSchema,
  text: LocalizedTextSchema,
  difficulty: z.number().int(),
  rubric: z.array(RubricItemSchema),
  followups: z.array(z.string()),
  target_competency: z.string(),
});
export type PlannedQuestion = z.infer<typeof PlannedQuestionSchema>;

export const QuestionPlanSchema = z.object({
  sections_order: z.array(SectionSchema),
  questions: z.array(PlannedQuestionSchema),
  time_budget_min: z.number().int(),
  language_mode: LanguageModeSchema,
});
export type QuestionPlan = z.infer<typeof QuestionPlanSchema>;
