import { existsSync, copyFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { LANGUAGES } from "@deepinterview/shared";

function findRepoRoot(start: string): string {
  let dir = start;
  for (let i = 0; i < 8; i += 1) {
    if (existsSync(join(dir, ".env.example"))) return dir;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return start;
}

export async function runInit(args: string[]): Promise<void> {
  const force = args.includes("--force");
  const root = findRepoRoot(process.cwd());
  const example = join(root, ".env.example");
  const target = join(root, ".env");

  if (!existsSync(example)) {
    console.error(`Could not find .env.example near ${root}`);
    process.exit(1);
  }
  if (existsSync(target) && !force) {
    console.error(".env already exists — re-run with --force to overwrite.");
    process.exit(1);
  }

  copyFileSync(example, target);
  console.log(`✓ Wrote ${target} from .env.example`);
  console.log(
    `DeepInterview supports ${LANGUAGES.length} languages (English-first).`,
  );
  console.log(
    "Open .env and fill in your provider keys. (Interactive wizard: coming soon.)",
  );
}
