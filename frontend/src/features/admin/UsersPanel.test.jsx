import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { api } from "../../api/client";
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

test("criar usuário envia os dados do formulário e recarrega a lista", async () => {
  api.adminListUsers.mockResolvedValueOnce([]).mockResolvedValueOnce([
    { id: 1, email: "novo@exemplo.test", is_admin: false, disabled: false },
  ]);
  api.adminCreateUser.mockResolvedValue({ id: 1, email: "novo@exemplo.test", is_admin: false });
  const user = userEvent.setup();

  render(<UsersPanel />);
  await user.type(await screen.findByLabelText(/E-mail/), "novo@exemplo.test");
  await user.type(screen.getByLabelText(/Senha inicial/), "senha-nova-123");
  await user.click(screen.getByRole("button", { name: /criar/i }));

  expect(api.adminCreateUser).toHaveBeenCalledWith("novo@exemplo.test", "senha-nova-123", false);
  expect(await screen.findByText("novo@exemplo.test")).toBeInTheDocument();
});
