import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  poweredByHeader: false,
  output: process.env.VERCEL ? undefined : "standalone",
  distDir: process.env.KAIROS_NEXT_BUILD_DIR || ".next",
  turbopack: { root: process.cwd() },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "SAMEORIGIN",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "X-DNS-Prefetch-Control",
            value: "on",
          },
        ],
      },
    ];
  },
};
export default nextConfig;
