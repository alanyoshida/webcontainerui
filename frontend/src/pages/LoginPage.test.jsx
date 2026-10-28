import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { api, ApiError } from "../api/client";
import LoginPage from "./LoginPage";

vi.mock("../api/client", () => {
  class ApiError extends Error {
    constructor(status, detail) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  }
  return { api: { me: vi.fn(), login: vi.fn() }, ApiError };
});

beforeEach(() => {
  api.me.mockRejectedValue(new Error("não autenticado"));
});

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>
  );
}

test("credencial inválida mostra mensagem genérica, sem distinguir o motivo", async () => {
  // o backend responde 401 idêntico para e-mail inexistente e senha errada;
  // a tela não deve tentar adivinhar qual dos dois foi.
  api.login.mockRejectedValue(new ApiError(401, "credenciais inválidas"));
  const user = userEvent.setup();

  renderLoginPage();
  await user.type(await screen.findByLabelText(/E-mail/), "alguem@exemplo.test");
  await user.type(screen.getByLabelText(/Senha/), "qualquer-coisa");
  await user.click(screen.getByRole("button", { name: /entrar/i }));

  expect(await screen.findByText("Credenciais inválidas.")).toBeInTheDocument();
});

test("login bem-sucedido não mostra erro", async () => {
  api.login.mockResolvedValue({ id: 1, email: "a@exemplo.test", is_admin: false });
  const user = userEvent.setup();

  renderLoginPage();
  await user.type(await screen.findByLabelText(/E-mail/), "a@exemplo.test");
  await user.type(screen.getByLabelText(/Senha/), "senha-correta-123");
  await user.click(screen.getByRole("button", { name: /entrar/i }));

  expect(screen.queryByText("Credenciais inválidas.")).not.toBeInTheDocument();
});
