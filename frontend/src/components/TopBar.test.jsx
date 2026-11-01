import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { useAuth } from "../auth/AuthContext";
import { useThemeMode } from "../theme/ThemeModeContext";
import TopBar from "./TopBar";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../theme/ThemeModeContext", () => ({
  useThemeMode: vi.fn(),
}));

function renderTopBar(user) {
  useAuth.mockReturnValue({ user, logout: vi.fn() });
  useThemeMode.mockReturnValue({ mode: "dark", setMode: vi.fn() });
  return render(
    <MemoryRouter>
      <TopBar />
    </MemoryRouter>
  );
}

test("administrador vê o botão Administração", () => {
  renderTopBar({ email: "admin@exemplo.test", is_admin: true });

  expect(screen.getByRole("button", { name: "Administração" })).toBeInTheDocument();
});

test("usuário comum não vê o botão Administração", () => {
  renderTopBar({ email: "user@exemplo.test", is_admin: false });

  expect(screen.queryByRole("button", { name: "Administração" })).not.toBeInTheDocument();
});

test("menu de Administração lista as 8 seções do console", async () => {
  const user = userEvent.setup();
  renderTopBar({ email: "admin@exemplo.test", is_admin: true });

  await user.click(screen.getByRole("button", { name: "Administração" }));

  for (const label of ["Usuários", "Grupos", "Catálogo", "AGENTS.md", "Skills", "MCP", "Acessos", "Métricas de uso"]) {
    expect(screen.getByRole("menuitem", { name: label })).toBeInTheDocument();
  }
});

test("seletor de tema lista as três opções e troca o modo ao escolher", async () => {
  const setMode = vi.fn();
  useThemeMode.mockReturnValue({ mode: "dark", setMode });
  useAuth.mockReturnValue({ user: { email: "user@exemplo.test", is_admin: false }, logout: vi.fn() });
  const user = userEvent.setup();

  render(
    <MemoryRouter>
      <TopBar />
    </MemoryRouter>
  );

  await user.click(screen.getByRole("button", { name: "Tema" }));
  expect(screen.getByRole("menuitem", { name: "Light" })).toBeInTheDocument();
  expect(screen.getByRole("menuitem", { name: "Dark" })).toBeInTheDocument();
  expect(screen.getByRole("menuitem", { name: "Pastel" })).toBeInTheDocument();

  await user.click(screen.getByRole("menuitem", { name: "Pastel" }));
  expect(setMode).toHaveBeenCalledWith("pastel");
});

test("menu do usuário mostra o e-mail no cabeçalho, Identidade SSH e Sair", async () => {
  const logout = vi.fn();
  useAuth.mockReturnValue({ user: { email: "user@exemplo.test", is_admin: false }, logout });
  useThemeMode.mockReturnValue({ mode: "dark", setMode: vi.fn() });
  const user = userEvent.setup();

  render(
    <MemoryRouter>
      <TopBar />
    </MemoryRouter>
  );

  await user.click(screen.getByRole("button", { name: "Menu do usuário" }));

  const menu = screen.getByRole("menu");
  expect(within(menu).getByText("user@exemplo.test")).toBeInTheDocument();
  const sshLink = within(menu).getByRole("menuitem", { name: /Identidade SSH/ });
  expect(sshLink).toHaveAttribute("href", "/ssh-identity");

  await user.click(within(menu).getByRole("menuitem", { name: /Sair/ }));
  expect(logout).toHaveBeenCalledTimes(1);
});

test("avatar exibe as iniciais do e-mail do usuário", () => {
  renderTopBar({ email: "admin@local.test", is_admin: false });

  expect(screen.getByText("AL")).toBeInTheDocument();
});
