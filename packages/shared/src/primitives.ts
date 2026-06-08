import { z } from "zod";

export const LANGUAGES = [
  "en",
  "vi",
  "es",
  "zh",
  "hi",
  "id",
  "pt",
  "fr",
  "de",
  "ja",
] as const;
export const LanguageSchema = z.enum(LANGUAGES);
export type Language = z.infer<typeof LanguageSchema>;

export const LocalizedTextSchema = z
  .record(z.string(), z.string())
  .refine((v) => typeof v.en === "string" && v.en.length > 0, {
    message: "LocalizedText must include a non-empty 'en' entry",
  })
  .refine(
    (v) =>
      Object.keys(v).every((k) => (LANGUAGES as readonly string[]).includes(k)),
    {
      message: "LocalizedText contains an unsupported language key",
    },
  );
export type LocalizedText = z.infer<typeof LocalizedTextSchema>;

export const SectionSchema = z.enum([
  "intro",
  "behavioral",
  "technical",
  "coding",
  "wrap",
]);
export type Section = z.infer<typeof SectionSchema>;

export const SenioritySchema = z.enum([
  "intern",
  "junior",
  "mid",
  "senior",
  "staff",
  "principal",
]);
export type Seniority = z.infer<typeof SenioritySchema>;

export const MasteryLevelSchema = z.enum([
  "weak",
  "developing",
  "solid",
  "strong",
]);
export type MasteryLevel = z.infer<typeof MasteryLevelSchema>;

export const LanguageModeSchema = z.object({
  primary: LanguageSchema,
  mixed: z.boolean(),
});
export type LanguageMode = z.infer<typeof LanguageModeSchema>;
