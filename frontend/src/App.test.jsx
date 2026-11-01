import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import App from "./App";
import { api } from "./api/client";

vi.mock("./api/client", () => ({
  api: { me: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

test("rota raiz redireciona para o login quando não autenticado", async () => {
  api.me.mockRejectedValue(new Error("não autenticado"));

  render(<App />);

  expect(await screen.findByText("WebContainerUI")).toBeInTheDocument();
  expect(await screen.findByLabelText(/E-mail/)).toBeInTheDocument();
});
