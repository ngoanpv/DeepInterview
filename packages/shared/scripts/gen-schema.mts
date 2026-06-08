import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { SCHEMAS } from "../src/registry";

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, "..", "schema");
mkdirSync(outDir, { recursive: true });

function toJSONSchema(schema: unknown): unknown {
  const zz = z as unknown as {
    toJSONSchema?: (s: unknown, o?: unknown) => unknown;
  };
  if (typeof zz.toJSONSchema === "function") {
    // io: 'input' so fields with a `.default()` are NOT marked required,
    // matching Pydantic's (validation-mode) model_json_schema().
    return zz.toJSONSchema(schema, { target: "draft-2020-12", io: "input" });
  }
  throw new Error(
    "z.toJSONSchema is unavailable; install zod@^4 or wire zod-to-json-schema fallback",
  );
}

for (const [name, schema] of Object.entries(SCHEMAS)) {
  const json = toJSONSchema(schema);
  writeFileSync(
    join(outDir, `${name}.json`),
    JSON.stringify(json, null, 2) + "\n",
    "utf8",
  );
}
console.log(`Wrote ${Object.keys(SCHEMAS).length} schemas to ${outDir}`);
