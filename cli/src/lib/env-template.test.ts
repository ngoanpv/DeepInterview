import { describe, it, expect } from "vitest";
import { parseEnv, formatValue, renderEnv } from "./env-template";

const TEMPLATE = `# Comment header
NODE_ENV=development

# ── LLM ──
LLM_PROVIDER=gemini
GEMINI_API_KEY=
OPENAI_API_KEY=

# A commented example must be left untouched:
# EXAMPLE_KEY=do-not-edit
SEARCH_PROVIDER=mock
`;

describe("parseEnv", () => {
  it("reads KEY=VALUE pairs and skips comments / blanks / malformed lines", () => {
    const parsed = parseEnv(
      [
        "# c",
        "",
        "LLM_PROVIDER=gemini",
        "GEMINI_API_KEY=abc123",
        "junk-line",
      ].join("\n"),
    );
    expect(parsed).toEqual({
      LLM_PROVIDER: "gemini",
      GEMINI_API_KEY: "abc123",
    });
  });

  it("strips surrounding quotes from values", () => {
    expect(parseEnv("A=\"has spaces\"\nB='x'")).toEqual({
      A: "has spaces",
      B: "x",
    });
  });
});

describe("formatValue", () => {
  it("leaves simple values bare and quotes ones needing it", () => {
    expect(formatValue("sk-123")).toBe("sk-123");
    expect(formatValue("")).toBe("");
    expect(formatValue("has space")).toBe('"has space"');
    expect(formatValue("has#hash")).toBe('"has#hash"');
  });
});

describe("renderEnv", () => {
  it("overlays values while preserving comments, order, and blank lines", () => {
    const out = renderEnv(TEMPLATE, {
      LLM_PROVIDER: "openai",
      OPENAI_API_KEY: "sk-test",
      SEARCH_PROVIDER: "tavily",
    });
    expect(out).toContain("# Comment header");
    expect(out).toContain("# ── LLM ──");
    expect(out).toContain("LLM_PROVIDER=openai");
    expect(out).toContain("OPENAI_API_KEY=sk-test");
    expect(out).toContain("SEARCH_PROVIDER=tavily");
    // Untouched template defaults remain.
    expect(out).toContain("NODE_ENV=development");
    expect(out).toContain("GEMINI_API_KEY=");
    // A commented-out example line is never rewritten.
    expect(out).toContain("# EXAMPLE_KEY=do-not-edit");
  });

  it("appends keys that are not present in the template", () => {
    const out = renderEnv(TEMPLATE, { RAG_BACKEND: "lightrag" });
    expect(out).toContain("Added by `deepinterview init`");
    expect(out).toContain("RAG_BACKEND=lightrag");
  });

  it("round-trips: render then parse recovers the overlaid values", () => {
    const out = renderEnv(TEMPLATE, {
      GEMINI_API_KEY: "secret key with spaces",
      LLM_PROVIDER: "gemini",
    });
    const parsed = parseEnv(out);
    expect(parsed.GEMINI_API_KEY).toBe("secret key with spaces");
    expect(parsed.LLM_PROVIDER).toBe("gemini");
  });
});
