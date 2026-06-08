#!/usr/bin/env bash
set -euo pipefail

# DeepInterview dev setup — installs JS + Python deps.
echo "Installing JS workspace deps (pnpm)…"
pnpm install

echo "Syncing Python agent deps (uv)…"
( cd apps/agent && uv sync )

echo "Done. Next: pnpm deepinterview init && pnpm build && pnpm test"
