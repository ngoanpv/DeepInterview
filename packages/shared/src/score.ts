import { z } from "zod";
import { MasteryLevelSchema } from "./primitives";

export const CompetencyScoreSchema = z.object({
  competency: z.string(),
  score: z.number(),
  evidence: z.string(),
  level: MasteryLevelSchema,
});
export type CompetencyScore = z.infer<typeof CompetencyScoreSchema>;

export const LanguageReportSchema = z.object({
  fluency_score: z.number(),
  filler_word_count: z.number().int(),
  clarity_score: z.number(),
  code_switching_notes: z.string(),
  pronunciation_notes: z.string(),
  summary: z.string(),
});
export type LanguageReport = z.infer<typeof LanguageReportSchema>;

export const ModelAnswerSchema = z.object({
  question_id: z.string(),
  answer: z.string(),
});
export type ModelAnswer = z.infer<typeof ModelAnswerSchema>;

export const ScoreCardSchema = z.object({
  overall_score: z.number(),
  competency_scores: z.array(CompetencyScoreSchema),
  strengths: z.array(z.string()),
  weaknesses: z.array(z.string()),
  weak_competencies: z.array(z.string()),
  model_answers: z.array(ModelAnswerSchema),
  next_steps: z.array(z.string()),
  language_report: LanguageReportSchema,
  summary: z.string(),
});
export type ScoreCard = z.infer<typeof ScoreCardSchema>;
