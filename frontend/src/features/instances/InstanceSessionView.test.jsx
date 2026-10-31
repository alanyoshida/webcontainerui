import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import InstanceSessionView from "./InstanceSessionView";

beforeEach(() => {
  // InstanceSession checa a disponibilidade da sessão via fetch antes de
  // montar o iframe; aqui só interessa que ela resolva OK.
  global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
});

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

test("instância em execução mostra a sessão embutida", async () => {
  render(
    <InstanceSessionView
      instance={instance()}
      idleTimeoutMinutes={30}
      onBack={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(await screen.findByTitle(/Sessão da instância inst-1/)).toBeInTheDocument();
});

test("botão voltar chama onBack", async () => {
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={onBack} onStop={vi.fn()} onDelete={vi.fn()} />
  );

  await user.click(screen.getByRole("button", { name: /voltar/i }));

  expect(onBack).toHaveBeenCalledTimes(1);
});

test("parar chama onStop e permanece na visão (não chama onBack)", async () => {
  const onStop = vi.fn();
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={onBack} onStop={onStop} onDelete={vi.fn()} />
  );

  await user.click(screen.getByRole("button", { name: "Parar" }));

  expect(onStop).toHaveBeenCalledWith("inst-1");
  expect(onBack).not.toHaveBeenCalled();
});

test("excluir pede confirmação e, confirmado, chama onDelete seguido de onBack", async () => {
  const onDelete = vi.fn();
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={onBack} onStop={vi.fn()} onDelete={onDelete} />
  );

  await user.click(screen.getByRole("button", { name: "Excluir" }));
  expect(onDelete).not.toHaveBeenCalled();
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Excluir instância?")).toBeInTheDocument();

  await user.click(within(dialog).getByRole("button", { name: "Excluir" }));

  expect(onDelete).toHaveBeenCalledWith("inst-1");
  expect(onBack).toHaveBeenCalledTimes(1);
});

test("cancelar a exclusão não chama onDelete nem onBack", async () => {
  const onDelete = vi.fn();
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={onBack} onStop={vi.fn()} onDelete={onDelete} />
  );

  await user.click(screen.getByRole("button", { name: "Excluir" }));
  await user.click(screen.getByRole("button", { name: /cancelar/i }));

  expect(onDelete).not.toHaveBeenCalled();
  expect(onBack).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.queryByText("Excluir instância?")).not.toBeInTheDocument());
});

test("instância parada mostra o aviso de parada em vez da sessão, sem botão Parar", () => {
  render(
    <InstanceSessionView
      instance={instance({ state: "stopped" })}
      idleTimeoutMinutes={45}
      onBack={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(screen.getByText(/45 minutos/)).toBeInTheDocument();
  expect(screen.queryByTitle(/Sessão da instância/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Parar" })).not.toBeInTheDocument();
});

test("instância em erro mostra a mensagem de erro em vez da sessão", () => {
  render(
    <InstanceSessionView
      instance={instance({ state: "error", error_message: "docker indisponível" })}
      idleTimeoutMinutes={30}
      onBack={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(screen.getByText("docker indisponível")).toBeInTheDocument();
  expect(screen.queryByTitle(/Sessão da instância/)).not.toBeInTheDocument();
});
