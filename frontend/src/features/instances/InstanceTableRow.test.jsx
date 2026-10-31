import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import InstanceTableRow from "./InstanceTableRow";

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

function renderRow(props) {
  return render(
    <table>
      <tbody>
        <InstanceTableRow {...props} />
      </tbody>
    </table>
  );
}

test("nenhuma ação de pausa é oferecida, em nenhum estado", () => {
  for (const state of ["running", "stopped", "starting", "error"]) {
    const { unmount } = renderRow({
      instance: instance({ state }),
      idleTimeoutMinutes: 30,
      onOpenSession: vi.fn(),
      onStart: vi.fn(),
      onStop: vi.fn(),
      onDelete: vi.fn(),
    });
    expect(screen.queryByRole("button", { name: /pausar/i })).not.toBeInTheDocument();
    unmount();
  }
});

test("excluir pede confirmação antes de chamar onDelete", async () => {
  const onDelete = vi.fn();
  const user = userEvent.setup();
  renderRow({
    instance: instance(),
    idleTimeoutMinutes: 30,
    onOpenSession: vi.fn(),
    onStart: vi.fn(),
    onStop: vi.fn(),
    onDelete,
  });

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
  renderRow({
    instance: instance(),
    idleTimeoutMinutes: 30,
    onOpenSession: vi.fn(),
    onStart: vi.fn(),
    onStop: vi.fn(),
    onDelete,
  });

  await user.click(screen.getByRole("button", { name: /excluir/i }));
  await user.click(screen.getByRole("button", { name: /cancelar/i }));

  expect(onDelete).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.queryByText("Excluir instância?")).not.toBeInTheDocument());
});

test("instância parada mostra o limite de inatividade configurado", () => {
  renderRow({
    instance: instance({ state: "stopped" }),
    idleTimeoutMinutes: 45,
    onOpenSession: vi.fn(),
    onStart: vi.fn(),
    onStop: vi.fn(),
    onDelete: vi.fn(),
  });

  expect(screen.getByText(/45 minutos/)).toBeInTheDocument();
});

test("clicar em abrir sessão chama onOpenSession com o id da instância", async () => {
  const onOpenSession = vi.fn();
  const user = userEvent.setup();
  renderRow({
    instance: instance(),
    idleTimeoutMinutes: 30,
    onOpenSession,
    onStart: vi.fn(),
    onStop: vi.fn(),
    onDelete: vi.fn(),
  });

  await user.click(screen.getByRole("button", { name: "Abrir sessão" }));

  expect(onOpenSession).toHaveBeenCalledWith("inst-1");
});

test("instância em execução oferece abrir sessão, parar e excluir; sem iniciar", () => {
  renderRow({
    instance: instance({ state: "running" }),
    idleTimeoutMinutes: 30,
    onOpenSession: vi.fn(),
    onStart: vi.fn(),
    onStop: vi.fn(),
    onDelete: vi.fn(),
  });

  expect(screen.getByRole("button", { name: "Abrir sessão" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Parar" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Excluir" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Iniciar" })).not.toBeInTheDocument();
});

test("instância parada ou em erro oferece iniciar e excluir; sem abrir sessão nem parar", () => {
  for (const state of ["stopped", "error"]) {
    const { unmount } = renderRow({
      instance: instance({ state }),
      idleTimeoutMinutes: 30,
      onOpenSession: vi.fn(),
      onStart: vi.fn(),
      onStop: vi.fn(),
      onDelete: vi.fn(),
    });

    expect(screen.getByRole("button", { name: "Iniciar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Excluir" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Abrir sessão" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Parar" })).not.toBeInTheDocument();
    unmount();
  }
});

test("instância em erro mostra a mensagem de erro", () => {
  renderRow({
    instance: instance({ state: "error", error_message: "docker indisponível" }),
    idleTimeoutMinutes: 30,
    onOpenSession: vi.fn(),
    onStart: vi.fn(),
    onStop: vi.fn(),
    onDelete: vi.fn(),
  });

  expect(screen.getByText("docker indisponível")).toBeInTheDocument();
});
