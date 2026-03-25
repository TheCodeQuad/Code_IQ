import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async redirects() {
    return [
      {
        source: "/dashboard/analysis/:id/documentation",
        destination: "/dashboard/analysis/:id/results/documentation",
        permanent: false,
      },
      {
        source: "/dashboard/analysis/:id/metrics",
        destination: "/dashboard/analysis/:id/results/metrics",
        permanent: false,
      },
    ]
  },
  turbopack: {
    root: __dirname,
  },
}

export default nextConfig
