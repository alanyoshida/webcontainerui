import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND_URL = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    proxy: {
      // Em dev, o Vite faz o papel da origem única que em produção é o
      // FastAPI: tudo sob /api, /i e /uploads precisa parecer same-origin (D1).
      "/api": { target: BACKEND_URL, changeOrigin: true },
      "/i": { target: BACKEND_URL, changeOrigin: true, ws: true },
      "/uploads": { target: BACKEND_URL, changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.js",
    server: {
      // @mui/x-charts importa subcaminhos como "@mui/material/styles" sem
      // extensão de arquivo; @mui/material não declara "exports" no
      // package.json, então o resolvedor nativo de ESM do Node (usado pelo
      // Vitest para dependências externas) rejeita isso como "directory
      // import". Marcar como inline faz o Vitest resolver via Vite, que
      // tolera esse estilo de import (mesmo caminho que o build de
      // produção já usa sem problema).
      deps: { inline: ["@mui/x-charts"] },
    },
  },
});
