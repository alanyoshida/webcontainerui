import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { useAuth } from "../auth/AuthContext";
import TopBar from "./TopBar";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

test("link de Identidade SSH aponta para a área de identidade SSH", () => {
  useAuth.mockReturnValue({
    user: { email: "user@exemplo.test", is_admin: false },
    logout: vi.fn(),
  });

  render(
    <MemoryRouter>
      <TopBar />
    </MemoryRouter>
  );

  const link = screen.getByRole("link", { name: "Identidade SSH" });
  expect(link).toHaveAttribute("href", "/ssh-identity");
});

test("link de Identidade SSH aparece mesmo para usuário não administrador", () => {
  useAuth.mockReturnValue({
    user: { email: "user@exemplo.test", is_admin: false },
    logout: vi.fn(),
  });

  render(
    <MemoryRouter>
      <TopBar />
    </MemoryRouter>
  );

  expect(screen.getByRole("link", { name: "Identidade SSH" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Administração" })).not.toBeInTheDocument();
});
