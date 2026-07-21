import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  poweredByHeader: false,
  turbopack: { root: repositoryRoot },
  generateBuildId: async () => "inheritbench-web-v0.1",
};

export default nextConfig;
