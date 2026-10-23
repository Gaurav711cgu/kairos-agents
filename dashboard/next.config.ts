import { securityHeaders } from "./lib/security-headers";
import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  poweredByHeader: false,
  output: process.env.VERCEL ? undefined : "standalone",
  distDir: process.env.KAIROS_NEXT_BUILD_DIR || ".next",
  turbopack: { root: process.cwd() },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders(process.env.NODE_ENV === "development") }];
  },
};
export default nextConfig;
