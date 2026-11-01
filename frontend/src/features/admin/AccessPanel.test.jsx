import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { api } from "../../api/client";
import AccessPanel from "./AccessPanel";

vi.mock("../../api/client", () => ({
  api: {
    adminListGroups: vi.fn(),
    adminListImages: vi.fn(),
    adminListGroupImages: vi.fn(),
    adminGrantImage: vi.fn(),
    adminRevokePreview: vi.fn(),
    adminRevokeImage: vi.fn(),
  },
}));

beforeEach(() => {
  api.adminListGroups.mockResolvedValue([{ id: 1, name: "equipe" }]);
  api.adminListImages.mockResolvedValue([
    { id: 9, display_name: "Webtop", repository: "r", tag: "t" },
  ]);
  api.adminListGroupImages.mockResolvedValue([
    { id: 9, display_name: "Webtop", repository: "r", tag: "t" },
  ]);
});

test("sem grupo selecionado, instrui a selecionar um grupo", async () => {
  render(<AccessPanel />);

  expect(
    await screen.findByText("Selecione um grupo para ver e editar as permissões.")
  ).toBeInTheDocument();
});

test("revogação mostra o impacto antes de confirmar, e nada muda sem confirmar", async () => {
  api.adminRevokePreview.mockResolvedValue({ affected_instance_count: 3 });
  const user = userEvent.setup();

  render(<AccessPanel />);
  await user.click(await screen.findByLabelText("Grupo"));
  await user.click(await screen.findByRole("option", { name: "equipe" }));

  const chip = await screen.findByText("Webtop");
  const deleteIcon = chip.closest(".MuiChip-root").querySelector(".MuiChip-deleteIcon");
  await user.click(deleteIcon);

  expect(await screen.findByText(/3 instância\(s\) em execução serão paradas/)).toBeInTheDocument();
  expect(api.adminRevokeImage).not.toHaveBeenCalled(); // só a pré-visualização, nada revogado ainda

  const dialog = screen.getByRole("dialog");
  await user.click(within(dialog).getByRole("button", { name: /^revogar$/i }));

  expect(api.adminRevokeImage).toHaveBeenCalledWith(1, 9, true);
});
