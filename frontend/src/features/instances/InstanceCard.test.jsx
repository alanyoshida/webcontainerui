import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import InstanceCard from "./InstanceCard";

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

test("nenhuma ação de pausa é oferecida, em nenhum estado", async () => {
  for (const state of ["running", "stopped", "starting", "error"]) {
    const { unmount } = render(
      <InstanceCard instance={instance({ state })} idleTimeoutMinutes={30} onStart={vi.fn()} onStop={vi.fn()} onDelete={vi.fn()} />
    );
    expect(screen.queryByRole("button", { name: /pausar/i })).not.toBeInTheDocument();
    unmount();
  }
});

test("excluir pede confirmação antes de chamar onDelete", async () => {
  const onDelete = vi.fn();
  const user = userEvent.setup();
  render(<InstanceCard instance={instance()} idleTimeoutMinutes={30} onStart={vi.fn()} onStop={vi.fn()} onDelete={onDelete} />);

  await user.click(screen.getByRole("button", { name: /excluir/i }));
  expect(onDelete).not.toHaveBeenCalled(); // só abriu o diálogo, nada aconteceu ainda
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Excluir instância?")).toBeInTheDocument();

  await user.click(within(dialog).getByRole("button", { name: "Excluir" }));
  expect(onDelete).toHaveBeenCalledWith("inst-1");
});

test("cancelar a exclusão não chama onDelete", async () => {
  const onDelete = vi.fn();
  const user = userEvent.setup();
  render(<InstanceCard instance={instance()} idleTimeoutMinutes={30} onStart={vi.fn()} onStop={vi.fn()} onDelete={onDelete} />);

  await user.click(screen.getByRole("button", { name: /excluir/i }));
  await user.click(screen.getByRole("button", { name: /cancelar/i }));

  expect(onDelete).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.queryByText("Excluir instância?")).not.toBeInTheDocument());
});

test("instância parada mostra o limite de inatividade configurado", () => {
  render(
    <InstanceCard instance={instance({ state: "stopped" })} idleTimeoutMinutes={45} onStart={vi.fn()} onStop={vi.fn()} onDelete={vi.fn()} />
  );

  expect(screen.getByText(/45 minutos/)).toBeInTheDocument();
});

test("clicar em abrir/ocultar sessão chama onToggleSession, controlado pelo pai", async () => {
  const onToggleSession = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceCard
      instance={instance()}
      idleTimeoutMinutes={30}
      sessionOpen={false}
      onToggleSession={onToggleSession}
      onStart={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  await user.click(screen.getByRole("button", { name: "Abrir sessão" }));

  expect(onToggleSession).toHaveBeenCalledTimes(1);
});

test("sessionOpen=true exibe a sessão embutida quando a instância está em execução", () => {
  render(
    <InstanceCard
      instance={instance()}
      idleTimeoutMinutes={30}
      sessionOpen={true}
      onToggleSession={vi.fn()}
      onStart={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(screen.getByTitle(/Sessão da instância inst-1/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ocultar sessão" })).toBeInTheDocument();
});

test("instância em erro mostra a mensagem de erro", () => {
  render(
    <InstanceCard
      instance={instance({ state: "error", error_message: "docker indisponível" })}
      idleTimeoutMinutes={30}
      onStart={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(screen.getByText("docker indisponível")).toBeInTheDocument();
});
