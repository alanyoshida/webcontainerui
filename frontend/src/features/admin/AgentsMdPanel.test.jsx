import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { api, ApiError } from "../../api/client";
import AgentsMdPanel from "./AgentsMdPanel";

vi.mock("../../api/client", () => ({
  api: {
    adminListAgentsMd: vi.fn(),
    adminListImageAgentsMdLinks: vi.fn(),
    adminCreateAgentsMd: vi.fn(),
    adminUpdateAgentsMd: vi.fn(),
    adminDeleteAgentsMd: vi.fn(),
    adminSetImageAgentsMd: vi.fn(),
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
  api.adminListAgentsMd.mockResolvedValue([
    { id: 1, name: "Padrão", content: "# Regras", linked_images: 1, updated_at: null },
  ]);
  api.adminListImageAgentsMdLinks.mockResolvedValue([
    { id: 7, display_name: "Claude Code", repository: "wcui-agent-claude-code", tag: "latest", document_id: 1 },
    { id: 9, display_name: "Webtop", repository: "lscr.io/linuxserver/webtop", tag: "latest", document_id: null },
  ]);
  api.adminSetImageAgentsMd.mockResolvedValue({ propagation_failures: [] });
});

test("lista documentos e imagens com vínculo atual", async () => {
  render(<AgentsMdPanel />);

  expect((await screen.findAllByText("Padrão")).length).toBeGreaterThan(0);
  expect(screen.getByText("1 imagem")).toBeInTheDocument();
  expect(screen.getByText(/Claude Code/)).toBeInTheDocument();
  expect(screen.getByText(/Webtop/)).toBeInTheDocument();
});

test("cria um novo documento pelo diálogo", async () => {
  const user = userEvent.setup();
  api.adminCreateAgentsMd.mockResolvedValue({});
  render(<AgentsMdPanel />);

  await user.click(await screen.findByRole("button", { name: "Novo documento" }));
  await user.type(await screen.findByLabelText(/^Nome/), "Novo texto");
  await user.type(screen.getByLabelText(/Conteúdo/), "# Regras novas");
  await user.click(screen.getByRole("button", { name: "Salvar" }));

  await waitFor(() => {
    expect(api.adminCreateAgentsMd).toHaveBeenCalledWith({
      name: "Novo texto",
      content: "# Regras novas",
    });
  });
});

test("edita um documento existente", async () => {
  const user = userEvent.setup();
  api.adminUpdateAgentsMd.mockResolvedValue({});
  render(<AgentsMdPanel />);

  await user.click(await screen.findByRole("button", { name: "Editar" }));
  const campoNome = await screen.findByLabelText(/^Nome/);
  await user.clear(campoNome);
  await user.type(campoNome, "Padrão v2");
  await user.click(screen.getByRole("button", { name: "Salvar" }));

  await waitFor(() => {
    expect(api.adminUpdateAgentsMd).toHaveBeenCalledWith(1, {
      name: "Padrão v2",
      content: "# Regras",
    });
  });
});

test("vincula documento a uma imagem pelo seletor", async () => {
  const user = userEvent.setup();
  render(<AgentsMdPanel />);

  const seletores = await screen.findAllByRole("combobox");
  const seletorWebtop = seletores[1]; // segunda linha: Webtop, sem vínculo
  await user.click(seletorWebtop);
  await user.click(await screen.findByRole("option", { name: "Padrão" }));

  await waitFor(() => {
    expect(api.adminSetImageAgentsMd).toHaveBeenCalledWith(9, 1);
  });
});

test("vincular com sucesso mostra confirmação visual distinta de erro", async () => {
  const user = userEvent.setup();
  render(<AgentsMdPanel />);

  const seletores = await screen.findAllByRole("combobox");
  await user.click(seletores[1]);
  await user.click(await screen.findByRole("option", { name: "Padrão" }));

  expect(await screen.findByText("Vínculo salvo.")).toBeInTheDocument();
});

test("remover documento com erro mostra a mensagem do backend", async () => {
  const user = userEvent.setup();
  api.adminDeleteAgentsMd.mockRejectedValue(
    new ApiError(409, "documento AGENTS.md vinculado a 1 imagem(ns): desvincule antes de remover")
  );
  render(<AgentsMdPanel />);

  await user.click(await screen.findByRole("button", { name: "Remover" }));

  expect(await screen.findByText(/desvincule antes de remover/)).toBeInTheDocument();
  expect(api.adminDeleteAgentsMd).toHaveBeenCalledWith(1);
});

test("estado vazio explica como começar", async () => {
  api.adminListAgentsMd.mockResolvedValue([]);
  render(<AgentsMdPanel />);

  expect(await screen.findByText(/Nenhum documento ainda/)).toBeInTheDocument();
});
