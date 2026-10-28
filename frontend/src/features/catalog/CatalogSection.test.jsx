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

test("entrada com imagem de capa exibe a imagem", async () => {
  api.getCatalog.mockResolvedValue([
    {
      id: 1,
      display_name: "Webtop",
      repository: "lscr.io/linuxserver/webtop",
      tag: "latest",
      icon_url: "/uploads/1-abc.png",
    },
  ]);

  render(<CatalogSection onStart={vi.fn()} />);
  await screen.findByText("Webtop");

  const img = screen.getByRole("img", { name: "Webtop" });
  expect(img).toHaveAttribute("src", "/uploads/1-abc.png");
});

test("entrada sem imagem de capa exibe o indicador padrão", async () => {
  api.getCatalog.mockResolvedValue([
    {
      id: 1,
      display_name: "Webtop",
      repository: "lscr.io/linuxserver/webtop",
      tag: "latest",
      icon_url: null,
    },
  ]);

  render(<CatalogSection onStart={vi.fn()} />);
  await screen.findByText("Webtop");

  expect(screen.queryByRole("img", { name: "Webtop" })).not.toBeInTheDocument();
});
