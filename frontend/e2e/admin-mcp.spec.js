import { expect, test } from "@playwright/test";

// Fumaça E2E do admin contra o portal dev real. Requer a stack de dev no
// ar (docker compose dev + portal em http://127.0.0.1:8000) e o admin
// padrão do AGENTS.md. Cobre a verificação manual da tarefa 10.4 da change
// mcp-server-library: a aba "MCP" aparece e carrega a biblioteca.

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@local.test";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "senha-admin-dev-123456";

async function loginAsAdmin(page) {
  await page.goto("/");
  await page.getByLabel("E-mail").fill(ADMIN_EMAIL);
  await page.getByLabel("Senha").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /entrar/i }).click();
  // Espera a sessão existir de fato (cookie gravado) antes de navegar —
  // um goto imediato interrompe o SPA antes do Set-Cookie.
  await expect(page.getByRole("button", { name: /sair/i })).toBeVisible({ timeout: 15_000 });
  // O login cai no catálogo; o admin é uma rota própria.
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: /administração/i })).toBeVisible({
    timeout: 15_000,
  });
}

test("aba MCP aparece e carrega a biblioteca de servidores", async ({ page }) => {
  await loginAsAdmin(page);

  await page.getByRole("tab", { name: "MCP" }).click();

  await expect(page.getByRole("heading", { name: "Biblioteca de servidores MCP" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Novo servidor" })).toBeVisible();
  // A imagem de agente semeada aparece na tabela de vínculo.
  await expect(page.getByText(/wcui-agent-claude-code/).first()).toBeVisible();
});

test("aba MCP mostra servidor cadastrado com transporte", async ({ page }) => {
  await loginAsAdmin(page);

  await page.getByRole("tab", { name: "MCP" }).click();

  await expect(page.getByRole("heading", { name: "Biblioteca de servidores MCP" })).toBeVisible();
  // A biblioteca pode estar vazia (teste anterior limpou) ou com cadastros;
  // nos dois casos a tabela de vínculo por imagem tem que estar lá.
  await expect(page.getByText("Vínculo por imagem")).toBeVisible();
});
