import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The app is almost entirely client-rendered (TanStack Query against FastAPI), so we keep the
  // classic rendering model instead of Cache Components.
  cacheComponents: false,
  // Teacher pages live under /teacher; keep old links and bookmarks working.
  async redirects() {
    return [
      { source: "/dashboard", destination: "/teacher", permanent: true },
      { source: "/studio", destination: "/teacher/studio", permanent: true },
      { source: "/studio/:id", destination: "/teacher/studio/:id", permanent: true },
      { source: "/arena", destination: "/teacher/games", permanent: true },
      { source: "/students/:id", destination: "/teacher/students/:id", permanent: true },
    ];
  },
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
