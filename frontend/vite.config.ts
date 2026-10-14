/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `npm run dev` proxies /api to :8000, which is either the real backend or the Prism mock
// server started with `npm run mock`, so the UI can be built before the backend exists.
export default defineConfig(() => ({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    css: false,
    coverage: { include: ["src/**/*.{ts,tsx}"], exclude: ["src/api/schema.d.ts", "src/main.tsx"] },
  },
}));
