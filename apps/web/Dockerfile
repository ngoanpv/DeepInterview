# DeepInterview web (Next.js 15, App Router) — production image (WP-12).
#
# Multi-stage, Next.js *standalone* output (see apps/web/next.config.ts:
# `output: 'standalone'`). The final image is a slim `node server.js` with no
# install step at runtime.
#
# BUILD CONTEXT = repo root (this is a pnpm + Turborepo monorepo; the web app
# depends on the `@deepinterview/shared` workspace package, which must be built
# first). Build from the root:
#
#     docker build -f apps/web/Dockerfile -t deepinterview-web .
#
# (docker-compose.yml already sets `context: .` + this dockerfile.)

# ---- deps: install the full workspace (need every member's manifest) --------
FROM node:22-slim AS deps
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /repo

# Copy lockfile + workspace config + every package manifest first for caching.
# pnpm needs ALL workspace members' package.json to resolve the lockfile.
COPY pnpm-lock.yaml pnpm-workspace.yaml .npmrc package.json ./
COPY apps/web/package.json apps/web/package.json
COPY apps/agent/package.json apps/agent/package.json
COPY packages/shared/package.json packages/shared/package.json
COPY cli/package.json cli/package.json
RUN pnpm install --frozen-lockfile

# ---- builder: build @deepinterview/shared then the web app ------------------
FROM node:22-slim AS builder
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /repo

# NEXT_PUBLIC_* vars are inlined into the browser bundle at BUILD time by
# Next.js — values injected at runtime (compose env_file) never reach client
# code. Accept them as build args here and export them as env so `pnpm build`
# bakes them in. docker-compose.yml wires these from the root .env via
# `build.args` (see the web service). Hosted-only billing vars
# (NEXT_PUBLIC_PADDLE_*) are intentionally not plumbed — the OSS compose
# path runs without billing.
ARG NEXT_PUBLIC_APP_URL
ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_SENTRY_DSN
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN

# Bring in installed node_modules, then the full source tree.
COPY --from=deps /repo/node_modules ./node_modules
COPY . .

# Some Next projects expect apps/web/public to exist; guarantee it so the
# runner COPY below never fails even when there are no static assets yet.
RUN mkdir -p apps/web/public

# Turbo builds the `@deepinterview/shared` dependency first (^build), then web.
RUN pnpm build --filter @deepinterview/web...

# ---- runner: slim standalone server ----------------------------------------
FROM node:22-slim AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
WORKDIR /app

# Run as a non-root user.
RUN groupadd --system --gid 1001 nodejs \
 && useradd --system --uid 1001 --gid nodejs nextjs

# The standalone output already contains a minimal node_modules + the nested
# monorepo layout (apps/web/server.js, packages/shared, …). Copy it whole,
# then layer in static assets + public (Next does NOT bundle these).
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/public ./apps/web/public

USER nextjs
EXPOSE 3000

# Standalone entry is the nested path in a pnpm monorepo.
CMD ["node", "apps/web/server.js"]
