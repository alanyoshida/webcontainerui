import { expect, test } from "@playwright/test";

// Verificação da tarefa 11.3 da change mcp-server-library: forçar uma
// quebra de contrato (campo que o tradutor não preenche direito) e
// confirmar que o admin vê o alerta nomeando o MCP e o campo na tela.
//
// A quebra é forçada via banco (args com tipo errado — string em vez de
// lista), porque as validações de cadastro/API recusariam: é exatamente o
// cenário do design.md de um bug de tradutor/mudança de versão passando
// pelo cadastro são. O ajuste no SQLite usa o python do próprio container
// do portal (disponível por ser o runtime do backend).
//
// O alerta só existe quando há instância viva para propagar — o teste cria
// uma instância de Claude Code antes de vincular.

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@local.test";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "senha-admin-dev-123456";
const MCP_NAME = `Quebrado E2E ${Date.now()}`;
const PORTAL_CONTAINER = process.env.E2E_PORTAL_CONTAINER || "deploy-portal-1";
const CLAUDE_IMAGE_ID = 4; // wcui-agent-claude-code (seed do catálogo)

async function loginAsAdmin(page) {
  await page.goto("/");
  await page.getByLabel("E-mail").fill(ADMIN_EMAIL);
  await page.getByLabel("Senha").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /entrar/i }).click();
  await expect(page.getByRole("button", { name: /sair/i })).toBeVisible({ timeout: 15_000 });
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: /administração/i })).toBeVisible({
    timeout: 15_000,
  });
}

async function apiLogin(request) {
  const resp = await request.post("/api/auth/login", {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  });
  return resp.headers()["set-cookie"].split(";")[0];
}

test("vínculo com MCP quebrado mostra alerta nomeando o campo", async ({ page, request }) => {
  const cookie = await apiLogin(request);
  const headers = { cookie };

  // 0. Auto-limpeza: execuções anteriores interrompidas podem ter deixado
  //    MCPs de teste (o desvínculo/removedor só roda no fim do teste).
  const lista = await (await request.get("/api/admin/mcp-servers", { headers })).json();
  for (const mcp of lista.filter((m) => m.display_name.startsWith("Quebrado E2E"))) {
    await request.delete(`/api/admin/mcp-servers/${mcp.id}`, { headers });
  }

  // 1. Instância viva de Claude Code (sem ela não há propagação, e sem
  //    propagação não há validação pós-escrita nem alerta).
  const instanciada = await request.post("/api/instances", {
    headers,
    data: { image_id: CLAUDE_IMAGE_ID },
  });
  expect(instanciada.status()).toBe(201);
  const instanciaId = (await instanciada.json()).id;

  // 2. Cadastra um MCP válido pela API e o corrompe direto no banco
  //    (args = string, quebra o schema do claude-code).
  const criado = await request.post("/api/admin/mcp-servers", {
    headers,
    data: { display_name: MCP_NAME, transport: "stdio", command: "npx", args: ["-y"] },
  });
  expect(criado.status()).toBe(201);
  const mcpId = (await criado.json()).id;

  const { execFileSync } = await import("node:child_process");
  execFileSync("docker", [
    "exec",
    PORTAL_CONTAINER,
    "python",
    "-c",
    `import sqlite3; c = sqlite3.connect('/data/webcontainerui.db'); c.execute("UPDATE mcp_servers SET args_json = ? WHERE id = ?", ('"texto"', ${mcpId})); c.commit(); c.close()`,
  ]);

  try {
    // 3. Na tela, vincula o MCP à imagem Claude Code — a resposta traz
    //    schema_validation_errors e o painel mostra o alerta.
    await loginAsAdmin(page);
    await page.getByRole("tab", { name: "MCP" }).click();
    await expect(page.getByRole("heading", { name: "Biblioteca de servidores MCP" })).toBeVisible();

    const checkboxImagem = page
      .getByRole("row", { name: /Claude Code/ })
      .getByRole("checkbox", { name: new RegExp(MCP_NAME) });
    // Clique simples (o checkbox é controlado e só reflete o estado novo
    // depois do reload que segue à resposta do vínculo, que inclui a
    // propagação síncrona às instâncias vivas).
    await checkboxImagem.click();

    const alerta = page.getByTestId("schema-validation-alert");
    await expect(alerta).toBeVisible({ timeout: 30_000 });
    await expect(alerta).toContainText(`MCP '${MCP_NAME}'`);
    await expect(alerta).toContainText("campo 'args'");
  } finally {
    // 4. Limpeza via API, independente do resultado.
    await request.delete(`/api/admin/mcp-servers/images/${CLAUDE_IMAGE_ID}/servers/${mcpId}`, { headers });
    await request.delete(`/api/admin/mcp-servers/${mcpId}`, { headers });
    await request.delete(`/api/instances/${instanciaId}?confirm=true`, { headers });
  }
});
