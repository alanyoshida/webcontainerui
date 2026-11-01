import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { api, ApiError } from "../../api/client";
import SkillsPanel from "./SkillsPanel";

vi.mock("../../api/client", () => ({
  api: {
    adminListAgentSkills: vi.fn(),
    adminListImageAgentSkills: vi.fn(),
    adminCreateAgentSkill: vi.fn(),
    adminUpdateAgentSkill: vi.fn(),
    adminDeleteAgentSkill: vi.fn(),
    adminLinkAgentSkill: vi.fn(),
    adminUnlinkAgentSkill: vi.fn(),
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
  api.adminListAgentSkills.mockResolvedValue([
    {
      id: 1,
      display_name: "Vercel Optimize",
      repo_owner: "vercel-labs",
      repo_name: "agent-skills",
      subpath: "vercel-optimize",
      linked_images: 1,
      updated_at: null,
    },
  ]);
  api.adminListImageAgentSkills.mockResolvedValue([
    {
      id: 7,
      display_name: "Claude Code",
      repository: "wcui-agent-claude-code",
      tag: "latest",
      skill_ids: [1],
      pull_state: "ready",
      pull_progress: null,
      pull_error: null,
    },
    {
      id: 8,
      display_name: "OpenCode",
      repository: "wcui-agent-opencode",
      tag: "latest",
      skill_ids: [],
      pull_state: "ready",
      pull_progress: null,
      pull_error: null,
    },
  ]);
  api.adminLinkAgentSkill.mockResolvedValue({});
  api.adminUnlinkAgentSkill.mockResolvedValue({});
});

test("lista skills e imagens com vínculo atual", async () => {
  render(<SkillsPanel />);

  expect((await screen.findAllByText("Vercel Optimize")).length).toBeGreaterThan(0);
  expect(screen.getByText("1 imagem(ns)")).toBeInTheDocument();
  expect(screen.getByText(/Claude Code/)).toBeInTheDocument();
  expect(screen.getByText(/OpenCode/)).toBeInTheDocument();
  expect(screen.getByText("vercel-labs/agent-skills:vercel-optimize")).toBeInTheDocument();
});

test("cria uma nova skill pelo diálogo", async () => {
  const user = userEvent.setup();
  api.adminCreateAgentSkill.mockResolvedValue({});
  render(<SkillsPanel />);

  await user.click(await screen.findByRole("button", { name: "Nova skill" }));
  await user.type(await screen.findByLabelText(/Nome de exibição/), "Minha skill");
  await user.type(screen.getByLabelText(/Owner do GitHub/), "owner");
  await user.type(screen.getByLabelText(/^Repositório/), "repo");
  await user.click(screen.getByRole("button", { name: "Salvar" }));

  await waitFor(() => {
    expect(api.adminCreateAgentSkill).toHaveBeenCalledWith({
      display_name: "Minha skill",
      repo_owner: "owner",
      repo_name: "repo",
      subpath: "",
    });
  });
});

test("remove uma skill com erro mostra a mensagem do backend", async () => {
  const user = userEvent.setup();
  api.adminDeleteAgentSkill.mockRejectedValue(new ApiError(404, "skill não encontrada: 1"));
  render(<SkillsPanel />);

  await user.click(await screen.findByRole("button", { name: "Remover" }));

  expect(await screen.findByText(/skill não encontrada/)).toBeInTheDocument();
  expect(api.adminDeleteAgentSkill).toHaveBeenCalledWith(1);
});

test("alterna o vínculo pelo checkbox", async () => {
  const user = userEvent.setup();
  render(<SkillsPanel />);

  const checkboxes = await screen.findAllByRole("checkbox", { name: "Vercel Optimize" });
  // primeira linha (Claude Code) já vinculada; segunda (OpenCode) não
  expect(checkboxes[0]).toBeChecked();
  expect(checkboxes[1]).not.toBeChecked();

  await user.click(checkboxes[1]);
  await waitFor(() => {
    expect(api.adminLinkAgentSkill).toHaveBeenCalledWith(8, 1);
  });

  await user.click(checkboxes[0]);
  await waitFor(() => {
    expect(api.adminUnlinkAgentSkill).toHaveBeenCalledWith(7, 1);
  });
});

test("após vincular, mostra o estado de build em andamento", async () => {
  const user = userEvent.setup();
  api.adminLinkAgentSkill.mockResolvedValue({});
  render(<SkillsPanel />);

  // a partir da próxima chamada (disparada pelo reload após vincular), a
  // imagem volta com pull_state "pulling" e progresso do build
  api.adminListImageAgentSkills.mockResolvedValue([
    {
      id: 7,
      display_name: "Claude Code",
      repository: "wcui-agent-claude-code",
      tag: "latest",
      skill_ids: [1],
      pull_state: "ready",
      pull_progress: null,
      pull_error: null,
    },
    {
      id: 8,
      display_name: "OpenCode",
      repository: "wcui-agent-opencode",
      tag: "latest",
      skill_ids: [1],
      pull_state: "pulling",
      pull_progress: "Step 2/5 : RUN npm install",
      pull_error: null,
    },
  ]);

  const checkboxes = await screen.findAllByRole("checkbox", { name: "Vercel Optimize" });
  await user.click(checkboxes[1]); // vincula na imagem OpenCode (segunda linha)

  expect(await screen.findByText("Reconstruindo")).toBeInTheDocument();

  const checkboxesDepois = await screen.findAllByRole("checkbox", { name: "Vercel Optimize" });
  expect(checkboxesDepois[1]).toBeDisabled(); // não dá pra mexer de novo até o build terminar
});

test("progresso bruto do build (ex: caixa TUI do npx skills) não é exibido", async () => {
  // Linha real capturada do stream de build do `npx skills add`: desenha uma
  // caixa com bordas Unicode, ilegível como texto corrido — o chip de
  // estado já basta, o progresso bruto não é renderizado.
  const linhaCrua =
    "◇  Installation Summary ─────────╮ │ │ ~/.agents/skills/find-skills │ copy → OpenCode │ │ ╰─────────────────────╯";
  api.adminListImageAgentSkills.mockResolvedValue([
    {
      id: 7,
      display_name: "Claude Code",
      repository: "wcui-agent-claude-code",
      tag: "latest",
      skill_ids: [],
      pull_state: "ready",
      pull_progress: null,
      pull_error: null,
    },
    {
      id: 8,
      display_name: "OpenCode",
      repository: "wcui-agent-opencode",
      tag: "latest",
      skill_ids: [1],
      pull_state: "pulling",
      pull_progress: linhaCrua,
      pull_error: null,
    },
  ]);
  render(<SkillsPanel />);

  expect(await screen.findByText("Reconstruindo")).toBeInTheDocument();
  expect(screen.queryByText(/Installation Summary/)).not.toBeInTheDocument();
});

test("estado vazio explica como começar", async () => {
  api.adminListAgentSkills.mockResolvedValue([]);
  render(<SkillsPanel />);

  expect(await screen.findByText(/Nenhuma skill ainda/)).toBeInTheDocument();
});
