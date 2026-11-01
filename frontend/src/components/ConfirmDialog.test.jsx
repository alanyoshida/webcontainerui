import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import ConfirmDialog from "./ConfirmDialog";

test("renderiza título, descrição e botão de confirmação em vermelho com foco no cancelar", () => {
  render(
    <ConfirmDialog
      open
      title="Parar instância?"
      description="Os processos em execução são interrompidos; os arquivos permanecem salvos."
      confirmLabel="Parar"
      onCancel={vi.fn()}
      onConfirm={vi.fn()}
    />
  );

  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Parar instância?")).toBeInTheDocument();
  expect(
    within(dialog).getByText("Os processos em execução são interrompidos; os arquivos permanecem salvos.")
  ).toBeInTheDocument();

  const confirmButton = within(dialog).getByRole("button", { name: "Parar" });
  expect(confirmButton).toHaveClass("MuiButton-containedError");
  expect(within(dialog).getByRole("button", { name: "Cancelar" })).toHaveFocus();
});

test("não fechado: nada é confirmado até o clique no botão de confirmação", async () => {
  const onConfirm = vi.fn().mockResolvedValue();
  const onCancel = vi.fn();
  const user = userEvent.setup();
  render(
    <ConfirmDialog
      open
      title="Excluir grupo?"
      description="Isto remove o grupo."
      confirmLabel="Excluir"
      onCancel={onCancel}
      onConfirm={onConfirm}
    />
  );

  expect(onConfirm).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "Cancelar" }));
  expect(onCancel).toHaveBeenCalledTimes(1);
  expect(onConfirm).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "Excluir" }));
  expect(onConfirm).toHaveBeenCalledTimes(1);
});

test("desabilita os botões enquanto a confirmação está em andamento (busy)", async () => {
  let resolveConfirm;
  const onConfirm = vi.fn(
    () =>
      new Promise((resolve) => {
        resolveConfirm = resolve;
      })
  );
  const user = userEvent.setup();
  render(
    <ConfirmDialog
      open
      title="Remover servidor MCP?"
      description="Afeta instâncias vivas imediatamente."
      confirmLabel="Remover"
      onCancel={vi.fn()}
      onConfirm={onConfirm}
    />
  );

  await user.click(screen.getByRole("button", { name: "Remover" }));

  expect(screen.getByRole("button", { name: "Remover" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Cancelar" })).toBeDisabled();

  resolveConfirm();
  await waitFor(() => expect(screen.getByRole("button", { name: "Remover" })).not.toBeDisabled());
});
