import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, vi } from "vitest";
import HomePage from "./HomePage";
import { api } from "../api/client";

vi.mock("../api/client", () => ({
  api: {
    getCatalog: vi.fn(),
    getPublicConfig: vi.fn(),
    listInstances: vi.fn(),
    createInstance: vi.fn(),
    stopInstance: vi.fn(),
    deleteInstance: vi.fn(),
  },
}));

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
  api.getCatalog.mockResolvedValue([]);
  api.getPublicConfig.mockResolvedValue({ idle_timeout_minutes: 30 });
  global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
});

afterEach(() => {
  vi.useRealTimers();
});

test("por padrão mostra o catálogo e a tabela de instâncias, não a sessão", async () => {
  api.listInstances.mockResolvedValue([instance()]);

  render(<HomePage />);

  expect(await screen.findByRole("table")).toBeInTheDocument();
  expect(screen.getByText("Catálogo")).toBeInTheDocument();
  expect(screen.queryByTitle(/Sessão da instância/)).not.toBeInTheDocument();
});

test("abrir sessão troca a listagem pela visão dedicada; voltar restaura a listagem", async () => {
  api.listInstances.mockResolvedValue([instance()]);
  const user = userEvent.setup();

  render(<HomePage />);
  const table = await screen.findByRole("table");

  await user.click(within(table).getByRole("button", { name: /abrir sessão/i }));

  expect(await screen.findByTitle(/Sessão da instância inst-1/)).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByText("Catálogo")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /voltar/i }));

  expect(await screen.findByRole("table")).toBeInTheDocument();
  expect(screen.getByText("Catálogo")).toBeInTheDocument();
  expect(screen.queryByTitle(/Sessão da instância/)).not.toBeInTheDocument();
});

test("resumo 'Em execução agora' lista a instância em execução com atalho para abrir a sessão", async () => {
  api.listInstances.mockResolvedValue([instance()]);

  render(<HomePage />);

  const card = await screen.findByRole("region", { name: "Em execução agora" });
  expect(within(card).getByText("Webtop")).toBeInTheDocument();
  expect(within(card).getByRole("button", { name: /abrir sessão/i })).toBeInTheDocument();
});

test("resumo sem instâncias em execução indica que não há nenhuma", async () => {
  api.listInstances.mockResolvedValue([instance({ state: "stopped" })]);

  render(<HomePage />);

  const card = await screen.findByRole("region", { name: "Em execução agora" });
  expect(within(card).getByText("Nenhuma instância em execução agora.")).toBeInTheDocument();
});

test("se a instância aberta sumir da lista (ex.: excluída em outro lugar), volta sozinho para a listagem", async () => {
  // Fake timers desde antes do mount: o poll de 5s de useInstances precisa
  // ser registrado já sob fake timers para vi.advanceTimersByTimeAsync
  // conseguir avançá-lo depois — por isso fireEvent (síncrono) no lugar de
  // userEvent, e flush manual de microtask no lugar de findBy/waitFor.
  vi.useFakeTimers();
  api.listInstances.mockResolvedValueOnce([instance()]).mockResolvedValue([]);

  render(<HomePage />);
  await act(async () => {
    await Promise.resolve();
  });
  const table = screen.getByRole("table");

  fireEvent.click(within(table).getByRole("button", { name: /abrir sessão/i }));
  await act(async () => {
    await Promise.resolve();
  });
  expect(screen.getByTitle(/Sessão da instância inst-1/)).toBeInTheDocument();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000); // próximo poll de useInstances devolve lista vazia
  });

  expect(screen.queryByTitle(/Sessão da instância/)).not.toBeInTheDocument();
  expect(screen.getByText("Catálogo")).toBeInTheDocument();
});
