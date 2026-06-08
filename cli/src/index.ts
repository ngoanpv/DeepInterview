import { runInit } from "./commands/init";

const [, , command, ...args] = process.argv;

function printHelp(): void {
  console.log(`deepinterview — DeepInterview CLI

Usage:
  deepinterview init [--force]   Create .env from .env.example

The interactive provider-key wizard arrives in a later milestone; for now
\`init\` copies .env.example to .env so you can fill in keys by hand.`);
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
