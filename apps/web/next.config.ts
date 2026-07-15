import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  poweredByHeader: false,
  turbopack: { root: new URL("../..", import.meta.url).pathname },
  generateBuildId: async () => "inheritbench-web-v0.1",
};

export default nextConfig;
