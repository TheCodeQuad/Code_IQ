import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  // Optimize for dynamic imports and client-side rendering
  experimental: {
    optimizePackageImports: ["cytoscape"],
  },
  webpack: (config, { isServer }) => {
    // Exclude cytoscape from server-side rendering
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        os: false,
      }
    }
    return config
  },
}

export default nextConfig
