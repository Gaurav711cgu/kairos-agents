import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  poweredByHeader: false,
  output: "standalone",
  distDir: process.env.KAIROS_NEXT_BUILD_DIR || ".next",
  turbopack: { root: process.cwd() },
};
export default nextConfig;
