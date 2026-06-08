import { z } from "zod";

export const CitationSchema = z.object({
  title: z.string(),
  url: z.string(),
  snippet: z.string().nullable().default(null),
});
export type Citation = z.infer<typeof CitationSchema>;

export const CompanyIntelSchema = z.object({
  name: z.string(),
  summary: z.string(),
  industry: z.string().nullable().default(null),
  tech_stack: z.array(z.string()),
  values: z.array(z.string()),
  interview_process: z.array(z.string()),
  recent_news: z.array(z.string()),
  citations: z.array(CitationSchema),
});
export type CompanyIntel = z.infer<typeof CompanyIntelSchema>;
