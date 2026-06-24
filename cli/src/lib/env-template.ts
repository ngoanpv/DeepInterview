/**
 * Pure, side-effect-free helpers for reading and rendering the project's `.env`
 * files. Kept dependency-free so the wizard's file logic is unit-testable
 * without a TTY or filesystem.
 */

const KEY_LINE = /^(\s*)([A-Z][A-Z0-9_]*)=(.*)$/;

function unquote(value: string): string {
  if (
    value.length >= 2 &&
    ((value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'")))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

/**
 * Parse `KEY=VALUE` pairs from a `.env` body into a map. Comments, blank lines
 * and malformed lines are skipped; surrounding quotes on a value are stripped.
 */
export function parseEnv(body: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of body.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    if (!/^[A-Z][A-Z0-9_]*$/.test(key)) continue;
    out[key] = unquote(line.slice(eq + 1).trim());
  }
  return out;
}

/**
 * Quote a value for a `.env` line only when it contains characters a dotenv
 * parser would otherwise split on (whitespace, `#`) or quotes. Empty stays empty.
 */
export function formatValue(value: string): string {
  if (value === "") return "";
  if (/[\s#"']/.test(value)) return `"${value.replace(/(["\\])/g, "\\$1")}"`;
  return value;
}

/**
 * Render a `.env` file by overlaying `values` onto the annotated `template`
 * (the `.env.example`), preserving its comments, ordering and blank lines. A key
 * present in the template takes `values[key]` when provided, else keeps its
 * template default. Keys in `values` absent from the template are appended under
 * a trailing section so nothing the caller asked for is silently dropped.
 */
export function renderEnv(
  template: string,
  values: Record<string, string>,
): string {
  const seen = new Set<string>();
  const lines = template.split(/\r?\n/).map((raw) => {
    const match = raw.match(KEY_LINE);
    if (!match) return raw;
    const indent = match[1] ?? "";
    const key = match[2];
    if (key === undefined) return raw;
    seen.add(key);
    if (Object.prototype.hasOwnProperty.call(values, key)) {
      return `${indent}${key}=${formatValue(values[key] ?? "")}`;
    }
    return raw;
  });

  const extras = Object.keys(values).filter((key) => !seen.has(key));
  if (extras.length > 0) {
    lines.push("");
    lines.push("# Added by `deepinterview init` (keys not in .env.example):");
    for (const key of extras)
      lines.push(`${key}=${formatValue(values[key] ?? "")}`);
  }
  return lines.join("\n");
}
