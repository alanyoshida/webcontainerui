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
  // InstanceSession checa a disponibilidade da sessão via fetch antes de
  // montar o iframe; aqui só interessa que ela resolva OK.
  global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
});

test("listagem em grade renderiza todas as instâncias do usuário", async () => {
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
      onStart={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(await screen.findByText("Webtop")).toBeInTheDocument();
  expect(screen.getByText("Ubuntu KDE")).toBeInTheDocument();
  expect(screen.getByText("Alpine XFCE")).toBeInTheDocument();
});

test("sessão embutida aberta ocupa a largura total do card, mesmo em listagem de múltiplas colunas", async () => {
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
      onStart={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );
  await screen.findByText("Webtop");

  const [abrirSessaoWebtop] = screen.getAllByRole("button", { name: /abrir sessão/i });
  await user.click(abrirSessaoWebtop);

  const sessao = await screen.findByTitle("Sessão da instância inst-1");
  expect(sessao).toHaveStyle({ width: "100%" });
});

test("abrir a sessão amplia o card para 80% da tela; os demais mantêm o tamanho normal", async () => {
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
      onStart={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );
  await screen.findByText("Webtop");

  const gridItemWebtop = screen.getByText("Webtop").closest(".MuiGrid-item");
  const gridItemUbuntu = screen.getByText("Ubuntu KDE").closest(".MuiGrid-item");
  expect(gridItemWebtop).not.toHaveStyle({ width: "80%" });

  const [abrirSessaoWebtop] = screen.getAllByRole("button", { name: /abrir sessão/i });
  await user.click(abrirSessaoWebtop);

  expect(gridItemWebtop).toHaveStyle({ width: "80%" });
  expect(gridItemUbuntu).not.toHaveStyle({ width: "80%" });
});

test("parar a instância com a sessão aberta devolve o card ao tamanho normal", async () => {
  const user = userEvent.setup();
  const onStop = vi.fn();
  const { rerender } = render(
    <InstancesSection
      instances={[instance({ id: "inst-1", image_display_name: "Webtop" })]}
      loading={false}
      error=""
      onStart={vi.fn()}
      onStop={onStop}
      onDelete={vi.fn()}
    />
  );
  await screen.findByText("Webtop");

  await user.click(screen.getByRole("button", { name: /abrir sessão/i }));
  const gridItem = screen.getByText("Webtop").closest(".MuiGrid-item");
  expect(gridItem).toHaveStyle({ width: "80%" });

  rerender(
    <InstancesSection
      instances={[instance({ id: "inst-1", image_display_name: "Webtop", state: "stopped" })]}
      loading={false}
      error=""
      onStart={vi.fn()}
      onStop={onStop}
      onDelete={vi.fn()}
    />
  );

  expect(screen.getByText("Webtop").closest(".MuiGrid-item")).not.toHaveStyle({ width: "80%" });
});
