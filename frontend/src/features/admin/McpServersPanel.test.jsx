import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { api, ApiError } from "../../api/client";
import McpServersPanel from "./McpServersPanel";

vi.mock("../../api/client", () => ({
  api: {
    adminListMcpServers: vi.fn(),
    adminListImageMcpServers: vi.fn(),
    adminCreateMcpServer: vi.fn(),
    adminUpdateMcpServer: vi.fn(),
    adminDeleteMcpServer: vi.fn(),
    adminLinkMcpServer: vi.fn(),
    adminUnlinkMcpServer: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(status, detail) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  api.adminListMcpServers.mockResolvedValue([
    {
      id: 1,
      display_name: "Contexto",
      transport: "stdio",
      command: "npx",
      args: ["-y", "mcp-server"],
      url: null,
      env_keys: ["API_KEY"],
      headers_keys: [],
      enabled: true,
      linked_images: 1,
      updated_at: null,
    },
  ]);
  api.adminListImageMcpServers.mockResolvedValue([
    {
      id: 7,
      display_name: "Claude Code",
      repository: "wcui-agent-claude-code",
      tag: "latest",
      mcp_server_ids: [1],
      propagation_failures: [],
      schema_validation_errors: [],
    },
    {
      id: 8,
      display_name: "OpenCode",
      repository: "wcui-agent-opencode",
      tag: "latest",
      mcp_server_ids: [],
      propagation_failures: [],
      schema_validation_errors: [],
    },
  ]);
  api.adminCreateMcpServer.mockResolvedValue({});
  api.adminUpdateMcpServer.mockResolvedValue({});
  api.adminDeleteMcpServer.mockResolvedValue({});
  api.adminLinkMcpServer.mockResolvedValue({});
  api.adminUnlinkMcpServer.mockResolvedValue({});
});

test("lista servidores e imagens com vínculo atual", async () => {
  render(<McpServersPanel />);

  expect((await screen.findAllByText("Contexto")).length).toBeGreaterThan(0);
  expect(screen.getByText("1 imagem(ns)")).toBeInTheDocument();
  expect(screen.getByText(/Claude Code/)).toBeInTheDocument();
  expect(screen.getByText(/OpenCode/)).toBeInTheDocument();
});

test("cria servidor stdio com comando e argumentos", async () => {
  const user = userEvent.setup();
  render(<McpServersPanel />);

  await user.click(await screen.findByRole("button", { name: "Novo servidor" }));
  await user.type(screen.getByLabelText("Nome de exibição *"), "Meu MCP");
  await user.type(screen.getByLabelText(/Comando/), "npx");
  await user.type(screen.getByLabelText(/Argumentos/), "-y @some/mcp-server");
  await user.click(screen.getByRole("button", { name: "Salvar" }));

  await waitFor(() => expect(api.adminCreateMcpServer).toHaveBeenCalled());
  expect(api.adminCreateMcpServer).toHaveBeenCalledWith({
    display_name: "Meu MCP",
    transport: "stdio",
    enabled: true,
    command: "npx",
    args: ["-y", "@some/mcp-server"],
  });
});

test("cria servidor remoto com URL e headers condicionais", async () => {
  const user = userEvent.setup();
  render(<McpServersPanel />);

  await user.click(await screen.findByRole("button", { name: "Novo servidor" }));
  await user.type(screen.getByLabelText("Nome de exibição *"), "Remoto");
  await user.click(screen.getByRole("combobox", { name: "Transporte" }));
  await user.click(screen.getByRole("option", { name: "http" }));
  await user.type(screen.getByLabelText(/URL/), "https://mcp.test/sse");
  await user.type(screen.getByLabelText(/Headers/), "Authorization=Bearer abc");
  await user.click(screen.getByRole("button", { name: "Salvar" }));

  await waitFor(() => expect(api.adminCreateMcpServer).toHaveBeenCalled());
  expect(api.adminCreateMcpServer).toHaveBeenCalledWith({
    display_name: "Remoto",
    transport: "http",
    enabled: true,
    url: "https://mcp.test/sse",
    headers: { Authorization: "Bearer abc" },
  });
});

test("remove servidor da biblioteca", async () => {
  const user = userEvent.setup();
  render(<McpServersPanel />);

  await user.click(await screen.findByRole("button", { name: "Remover" }));

  await waitFor(() => expect(api.adminDeleteMcpServer).toHaveBeenCalledWith(1));
});

test("alterna vínculo de imagem com checkbox", async () => {
  const user = userEvent.setup();
  render(<McpServersPanel />);

  const caixas = await screen.findAllByRole("checkbox", { name: "Contexto" });
  // A primeira caixa é a da primeira imagem (Claude Code, já vinculada);
  // desmarcar desvincula.
  await user.click(caixas[0]);

  await waitFor(() =>
    expect(api.adminUnlinkMcpServer).toHaveBeenCalledWith(7, 1)
  );
});

test("alerta quebra de contrato nomeando MCP e campo", async () => {
  const user = userEvent.setup();
  api.adminUnlinkMcpServer.mockResolvedValue({
    propagation_failures: [],
    schema_validation_errors: [
      {
        instance_id: "inst-1",
        error: "MCP 'Contexto': campo 'command' obrigatório ausente",
      },
    ],
  });
  render(<McpServersPanel />);

  const caixas = await screen.findAllByRole("checkbox", { name: "Contexto" });
  await user.click(caixas[0]);

  expect(
    await screen.findByTestId("schema-validation-alert")
  ).toHaveTextContent("MCP 'Contexto': campo 'command' obrigatório ausente");
});
