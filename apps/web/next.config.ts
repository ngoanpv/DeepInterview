import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@deepinterview/shared"],
  // WP-12: emit a self-contained server bundle (.next/standalone) so the
  // production Docker image is a slim `node server.js` with no node_modules
  // install at runtime. Additive — does not affect `next dev` / `next start`.
  output: "standalone",
};

export default nextConfig;
