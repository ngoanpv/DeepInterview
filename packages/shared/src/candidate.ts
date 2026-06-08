import { z } from "zod";
import { SenioritySchema } from "./primitives";

export const ProjectSchema = z.object({
  name: z.string(),
  description: z.string(),
  tech: z.array(z.string()),
});
export type Project = z.infer<typeof ProjectSchema>;

export const EducationSchema = z.object({
  institution: z.string(),
  degree: z.string(),
  field: z.string().nullable().default(null),
  year: z.number().int().nullable().default(null),
});
export type Education = z.infer<typeof EducationSchema>;

export const CandidateProfileSchema = z.object({
  name: z.string(),
  headline: z.string(),
  summary_120w: z.string(),
  years_experience: z.number().int(),
  seniority: SenioritySchema,
  skills: z.array(z.string()),
  projects: z.array(ProjectSchema),
  achievements: z.array(z.string()),
  education: z.array(EducationSchema),
  spoken_languages: z.array(z.string()),
  links: z.array(z.string()).default([]),
});
export type CandidateProfile = z.infer<typeof CandidateProfileSchema>;
