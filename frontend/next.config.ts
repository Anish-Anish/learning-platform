import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The app is almost entirely client-rendered (TanStack Query against FastAPI), so we keep the
  // classic rendering model instead of Cache Components.
  cacheComponents: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
