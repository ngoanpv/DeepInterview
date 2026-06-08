import { z } from "zod";

export const GapAnalysisSchema = z.object({
  strengths: z.array(z.string()),
  gaps: z.array(z.string()),
  probe_targets: z.array(z.string()),
  matched_skills: z.array(z.string()),
  missing_skills: z.array(z.string()),
  summary: z.string(),
});
export type GapAnalysis = z.infer<typeof GapAnalysisSchema>;
