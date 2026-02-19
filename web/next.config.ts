import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  // Ensure API routes are not included in static export
  skipTrailingSlashRedirect: true,
};

export default nextConfig;
