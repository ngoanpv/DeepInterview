import { existsSync, copyFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
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

/**
 * Mirror the root .env into an app-local copy. Local dev (`pnpm dev`) never
 * reads the root .env: the Python agent loads apps/agent/.env
 * (pydantic-settings, cwd-relative) and Next.js loads apps/web/.env.local —
 * so without these copies the wizard's output is dead config for local dev.
 *
 * Same semantics as the root file: create only when missing, overwrite with
 * --force. Skips quietly (with a note) when the app directory doesn't exist.
 */
function syncCopy(
  source: string,
  target: string,
  root: string,
  force: boolean,
): void {
  const label = relative(root, target);
  if (!existsSync(dirname(target))) {
    console.log(`- Skipped ${label} (directory not found)`);
    return;
  }
  if (existsSync(target) && !force) {
    console.log(`- Kept existing ${label} (use --force to overwrite)`);
    return;
  }
  copyFileSync(source, target);
  console.log(`✓ Wrote ${label}`);
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
    console.error(
      ".env already exists — re-run with --force to re-sync the local-dev " +
        "copies from it (apps/agent/.env, apps/web/.env.local).",
    );
    process.exit(1);
  }

  if (!existsSync(target)) {
    copyFileSync(example, target);
    console.log(`✓ Wrote ${target} from .env.example`);
  } else {
    // --force with an existing root .env: keep it — it holds the user's keys
    // and is the single place to edit. --force means "re-sync the local-dev
    // copies from the root .env", NOT "reset my keys from the template".
    // To start over from the template, delete .env and re-run init.
    console.log(`✓ Kept ${target} (sync source — your keys are preserved)`);
  }

  // Local-dev copies (see syncCopy docstring).
  syncCopy(target, join(root, "apps", "agent", ".env"), root, force);
  syncCopy(target, join(root, "apps", "web", ".env.local"), root, force);

  console.log(
    `DeepInterview supports ${LANGUAGES.length} languages (English-first).`,
  );
  console.log(`
How the files are used:
  .env                 → docker compose (the full stack)
  apps/agent/.env      → local dev: the Python agent (pnpm dev)
  apps/web/.env.local  → local dev: the Next.js app (pnpm dev)

Edit your provider keys in the ROOT .env only, then re-run
\`deepinterview init --force\` to re-sync the local-dev copies.
WARNING: --force OVERWRITES apps/agent/.env and apps/web/.env.local —
any edits made directly to those copies are lost (the root .env is kept).
(Interactive wizard: coming soon.)`);
}
