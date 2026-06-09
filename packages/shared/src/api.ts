import { z } from "zod";
import { CitationSchema } from "./company";
import { LanguageSchema, LanguageModeSchema } from "./primitives";
import { ScoreCardSchema } from "./score";

export const PrepRequestSchema = z.object({
  cv_url: z.string(),
  jd_text: z.string(),
  company: z.string(),
  language_mode: LanguageModeSchema,
  // Owning user (Supabase auth uid). Optional so the offline/dev path (no auth)
  // still validates; when present the agent stamps it on the `sessions` row so
  // the report's RLS read (`auth.uid() = user_id`) can see the row.
  user_id: z.string().optional(),
});
export type PrepRequest = z.infer<typeof PrepRequestSchema>;

export const PrepResponseSchema = z.object({
  session_id: z.string(),
});
export type PrepResponse = z.infer<typeof PrepResponseSchema>;

export const ScoreRequestSchema = z.object({
  session_id: z.string(),
});
export type ScoreRequest = z.infer<typeof ScoreRequestSchema>;

export const ScoreResponseSchema = z.object({
  session_id: z.string(),
  scorecard: ScoreCardSchema,
});
export type ScoreResponse = z.infer<typeof ScoreResponseSchema>;

export const KbIngestRequestSchema = z.object({
  user_id: z.string(),
  files: z.array(z.string()),
});
export type KbIngestRequest = z.infer<typeof KbIngestRequestSchema>;

export const KbIngestResponseSchema = z.object({
  track_id: z.string(),
});
export type KbIngestResponse = z.infer<typeof KbIngestResponseSchema>;

export const KbQueryRequestSchema = z.object({
  user_id: z.string(),
  query: z.string(),
  lang: LanguageSchema,
});
export type KbQueryRequest = z.infer<typeof KbQueryRequestSchema>;

export const KbQueryResponseSchema = z.object({
  answer: z.string(),
  citations: z.array(CitationSchema),
});
export type KbQueryResponse = z.infer<typeof KbQueryResponseSchema>;
