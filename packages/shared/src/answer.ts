import { z } from "zod";

export const AnswerRecordSchema = z.object({
  question_id: z.string(),
  transcript: z.string(),
  started_at: z.string(),
  ended_at: z.string(),
  duration_sec: z.number().nullable().default(null),
  followups_asked: z.array(z.string()).default([]),
});
export type AnswerRecord = z.infer<typeof AnswerRecordSchema>;
