import { z } from "zod";
import { SenioritySchema } from "./primitives";

export const JobSpecSchema = z.object({
  title: z.string(),
  company_name: z.string(),
  location: z.string().nullable().default(null),
  seniority: SenioritySchema,
  must_have: z.array(z.string()),
  nice_to_have: z.array(z.string()),
  responsibilities: z.array(z.string()),
  tech_stack: z.array(z.string()),
  raw_text: z.string(),
});
export type JobSpec = z.infer<typeof JobSpecSchema>;
