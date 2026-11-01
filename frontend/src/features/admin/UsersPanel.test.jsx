import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import UsersPanel from "./UsersPanel";

vi.mock("../../api/client", () => ({
  api: { adminListUsers: vi.fn(), adminCreateUser: vi.fn(), adminDisableUser: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(status, detail) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  },
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

beforeEach(() => {
  useAuth.mockReturnValue({ user: { id: 1, email: "admin@exemplo.test", is_admin: true } });
});

test("criar usuário envia os dados do formulário e recarrega a lista", async () => {
  api.adminListUsers.mockResolvedValueOnce([]).mockResolvedValueOnce([
    { id: 2, email: "novo@exemplo.test", is_admin: false, disabled: false },
  ]);
  api.adminCreateUser.mockResolvedValue({ id: 2, email: "novo@exemplo.test", is_admin: false });
  const user = userEvent.setup();

  render(<UsersPanel />);
  await user.type(await screen.findByLabelText(/E-mail/), "novo@exemplo.test");
  await user.type(screen.getByLabelText(/Senha inicial/), "senha-nova-123");
  await user.click(screen.getByRole("button", { name: /criar/i }));

  expect(api.adminCreateUser).toHaveBeenCalledWith("novo@exemplo.test", "senha-nova-123", false);
  expect(await screen.findByText("novo@exemplo.test")).toBeInTheDocument();
});

test("a própria linha do administrador logado não oferece a ação de desabilitar", async () => {
  api.adminListUsers.mockResolvedValue([
    { id: 1, email: "admin@exemplo.test", is_admin: true, disabled: false },
    { id: 2, email: "outro@exemplo.test", is_admin: false, disabled: false },
  ]);

  render(<UsersPanel />);

  const adminRow = (await screen.findByText("admin@exemplo.test")).closest("tr");
  expect(within(adminRow).queryByRole("button", { name: /desabilitar/i })).not.toBeInTheDocument();

  const outroRow = screen.getByText("outro@exemplo.test").closest("tr");
  expect(within(outroRow).getByRole("button", { name: /desabilitar/i })).toBeInTheDocument();
});

test("desabilitar exige confirmação com o e-mail da conta antes de chamar a API", async () => {
  api.adminListUsers.mockResolvedValue([
    { id: 1, email: "admin@exemplo.test", is_admin: true, disabled: false },
    { id: 2, email: "outro@exemplo.test", is_admin: false, disabled: false },
  ]);
  api.adminDisableUser.mockResolvedValue();
  const user = userEvent.setup();

  render(<UsersPanel />);
  await user.click(await screen.findByRole("button", { name: /desabilitar/i }));

  expect(api.adminDisableUser).not.toHaveBeenCalled();
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Desabilitar outro@exemplo.test?")).toBeInTheDocument();

  await user.click(within(dialog).getByRole("button", { name: "Desabilitar" }));

  expect(api.adminDisableUser).toHaveBeenCalledWith(2);
});
