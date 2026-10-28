import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND_URL = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    proxy: {
      // Em dev, o Vite faz o papel da origem única que em produção é o
      // FastAPI: tudo sob /api e /i precisa parecer same-origin (D1).
      "/api": { target: BACKEND_URL, changeOrigin: true },
      "/i": { target: BACKEND_URL, changeOrigin: true, ws: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.js",
  },
});
