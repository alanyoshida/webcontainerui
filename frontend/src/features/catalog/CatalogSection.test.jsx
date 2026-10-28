import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../../api/client";
import CatalogSection from "./CatalogSection";

vi.mock("../../api/client", () => ({ api: { getCatalog: vi.fn() } }));

test("catálogo vazio mostra estado vazio explicativo", async () => {
  api.getCatalog.mockResolvedValue([]);

  render(<CatalogSection onStart={vi.fn()} />);

  expect(
    await screen.findByText(/Nenhuma imagem disponível para você ainda/)
  ).toBeInTheDocument();
});

test("imagem do catálogo oferece o botão iniciar", async () => {
  api.getCatalog.mockResolvedValue([
    { id: 1, display_name: "Webtop", repository: "lscr.io/linuxserver/webtop", tag: "latest" },
  ]);

  render(<CatalogSection onStart={vi.fn()} />);

  expect(await screen.findByText("Webtop")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /iniciar/i })).toBeInTheDocument();
});
