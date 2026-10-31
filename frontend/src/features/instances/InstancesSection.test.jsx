import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { api } from "../../api/client";
import InstancesSection from "./InstancesSection";

vi.mock("../../api/client", () => ({ api: { getPublicConfig: vi.fn() } }));

function instance(overrides = {}) {
  return {
    id: "inst-1",
    image_id: 7,
    image_display_name: "Webtop",
    image_repository: "lscr.io/linuxserver/webtop",
    image_tag: "latest",
    state: "running",
    error_message: null,
    ...overrides,
  };
}

beforeEach(() => {
  api.getPublicConfig.mockResolvedValue({ idle_timeout_minutes: 30 });
});

test("listagem em tabela renderiza todas as instâncias do usuário", async () => {
  const instances = [
    instance({ id: "inst-1", image_display_name: "Webtop" }),
    instance({ id: "inst-2", image_display_name: "Ubuntu KDE" }),
    instance({ id: "inst-3", image_display_name: "Alpine XFCE" }),
  ];

  render(
    <InstancesSection
      instances={instances}
      loading={false}
      error=""
      onOpenSession={vi.fn()}
      onStart={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(await screen.findByText("Webtop")).toBeInTheDocument();
  expect(screen.getByText("Ubuntu KDE")).toBeInTheDocument();
  expect(screen.getByText("Alpine XFCE")).toBeInTheDocument();
  expect(screen.getByRole("table")).toBeInTheDocument();
});

test("clicar em abrir sessão de uma linha chama onOpenSession com o id dela, sem controlar sessão internamente", async () => {
  const onOpenSession = vi.fn();
  const user = userEvent.setup();
  const instances = [
    instance({ id: "inst-1", image_display_name: "Webtop" }),
    instance({ id: "inst-2", image_display_name: "Ubuntu KDE" }),
  ];

  render(
    <InstancesSection
      instances={instances}
      loading={false}
      error=""
      onOpenSession={onOpenSession}
      onStart={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );
  await screen.findByText("Webtop");

  const [abrirSessaoWebtop] = screen.getAllByRole("button", { name: /abrir sessão/i });
  await user.click(abrirSessaoWebtop);

  expect(onOpenSession).toHaveBeenCalledWith("inst-1");
  // nenhum iframe/sessão é montado aqui — abrir sessão é decisão de quem usa o componente
  expect(screen.queryByTitle(/Sessão da instância/)).not.toBeInTheDocument();
});
