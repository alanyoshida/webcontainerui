import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { api } from "../../api/client";
import GroupsPanel from "./GroupsPanel";

vi.mock("../../api/client", () => ({
  api: {
    adminListGroups: vi.fn(),
    adminListUsers: vi.fn(),
    adminCreateGroup: vi.fn(),
    adminDeleteGroup: vi.fn(),
    adminListMembers: vi.fn(),
    adminAddMember: vi.fn(),
    adminRemoveMember: vi.fn(),
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
  api.adminListUsers.mockResolvedValue([]);
});

test("excluir grupo mostra o número de membros e só exclui após confirmar", async () => {
  api.adminListGroups.mockResolvedValue([{ id: 1, name: "equipe" }]);
  api.adminListMembers.mockResolvedValue([{ id: 1, email: "a@x.test" }, { id: 2, email: "b@x.test" }]);
  const user = userEvent.setup();

  render(<GroupsPanel />);
  await user.click(await screen.findByRole("button", { name: /excluir/i }));

  expect(await screen.findByText(/2 membro\(s\)/)).toBeInTheDocument();
  expect(api.adminDeleteGroup).not.toHaveBeenCalled();

  const dialog = screen.getByRole("dialog");
  await user.click(within(dialog).getByRole("button", { name: /^excluir$/i }));

  expect(api.adminDeleteGroup).toHaveBeenCalledWith(1);
});

test("grupo sem membros informa que nenhuma conta é afetada", async () => {
  api.adminListGroups.mockResolvedValue([{ id: 1, name: "vazio" }]);
  api.adminListMembers.mockResolvedValue([]);
  const user = userEvent.setup();

  render(<GroupsPanel />);
  await user.click(await screen.findByRole("button", { name: /excluir/i }));

  expect(await screen.findByText("Este grupo não tem membros. As contas dos usuários não são afetadas.")).toBeInTheDocument();
});
