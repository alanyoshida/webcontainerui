import { defineConfig, devices } from "@playwright/test";

// Testes E2E do frontend contra o portal de desenvolvimento real
// (`deploy/docker-compose.dev.yml` + `npm run dev` do Vite, ou o build
// servido pelo próprio FastAPI em http://127.0.0.1:8000). O portal precisa
// estar no ar antes de rodar: `npm run test:e2e` não sobe a stack sozinho,
// porque o backend depende de Docker, rede interna e imagens de agente.
//
// Login dev: admin@local.test / senha-admin-dev-123456 (AGENTS.md).
const BASE_URL = process.env.E2E_BASE_URL || "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // os testes criam cadastros reais no banco dev
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
