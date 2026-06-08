import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  InterviewContextSchema,
  LocalizedTextSchema,
  SAMPLE_INTERVIEW_CONTEXT,
  SCHEMAS,
} from "../src/index";

const here = dirname(fileURLToPath(import.meta.url));
const fixturesDir = join(here, "..", "fixtures");

function readJson(name: string): unknown {
  return JSON.parse(readFileSync(join(fixturesDir, name), "utf8"));
}

describe("InterviewContext round-trip", () => {
  it("parses the sample fixture without throwing", () => {
    const fixture = readJson("interview-context.sample.json");
    expect(() => InterviewContextSchema.parse(fixture)).not.toThrow();
  });

  it("round-trips parsed object through JSON deep-equal", () => {
    const fixture = readJson("interview-context.sample.json");
    const parsed = InterviewContextSchema.parse(fixture);
    const roundTripped = JSON.parse(JSON.stringify(parsed));
    expect(roundTripped).toEqual(parsed);
  });

  it("validates SAMPLE_INTERVIEW_CONTEXT against the Zod refines (the /api/health payload)", () => {
    // SAMPLE_INTERVIEW_CONTEXT is only TS-typed; TS cannot check Zod refines
    // (en-required, difficulty 1-5, weight 0-1). Parse it so an invalid sample
    // fails here at test time, not at runtime when /api/health is hit.
    expect(() =>
      InterviewContextSchema.parse(SAMPLE_INTERVIEW_CONTEXT),
    ).not.toThrow();
    const parsedSample = InterviewContextSchema.parse(SAMPLE_INTERVIEW_CONTEXT);
    const parsedFixture = InterviewContextSchema.parse(
      readJson("interview-context.sample.json"),
    );
    expect(parsedSample).toEqual(parsedFixture);
  });
});

describe("LocalizedText en-required invariant", () => {
  it("rejects a localized text map missing the en entry", () => {
    const missingEn = readJson("localized-text-missing-en.invalid.json");
    const result = LocalizedTextSchema.safeParse(missingEn);
    expect(result.success).toBe(false);
  });

  it("accepts a localized text map with a non-empty en entry", () => {
    const result = LocalizedTextSchema.safeParse({
      en: "hello",
      vi: "xin chào",
    });
    expect(result.success).toBe(true);
  });
});

describe("SCHEMAS registry", () => {
  it("has exactly 28 entries", () => {
    expect(Object.keys(SCHEMAS)).toHaveLength(28);
  });
});
