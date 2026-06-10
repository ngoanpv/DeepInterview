import { runInit } from "./commands/init";

const [, , command, ...args] = process.argv;

function printHelp(): void {
  console.log(`deepinterview — DeepInterview CLI

Usage:
  deepinterview init [--force]   Create .env from .env.example and sync the
                                 local-dev copies

\`init\` writes three files:
  .env                 → read by docker compose (the full stack)
  apps/agent/.env      → read by the Python agent in local dev (pnpm dev)
  apps/web/.env.local  → read by the Next.js app in local dev (pnpm dev)

Edit your provider keys in the ROOT .env only, then re-run
\`deepinterview init --force\` to re-sync the local-dev copies.
WARNING: --force OVERWRITES apps/agent/.env and apps/web/.env.local with the
root .env (direct edits to the copies are lost; the root .env is kept).

The interactive provider-key wizard arrives in a later milestone; for now
\`init\` copies .env.example so you can fill in keys by hand.`);
}

async function main(): Promise<void> {
  switch (command) {
    case "init":
      await runInit(args);
      break;
    case undefined:
    case "help":
    case "--help":
    case "-h":
      printHelp();
      break;
    default:
      console.error(`Unknown command: ${command}\n`);
      printHelp();
      process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
