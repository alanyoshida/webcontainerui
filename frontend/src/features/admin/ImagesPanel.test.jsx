import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../../api/client";
import ImagesPanel from "./ImagesPanel";

vi.mock("../../api/client", () => ({
  api: {
    adminListImages: vi.fn(),
    adminCreateImage: vi.fn(),
    adminRetryPull: vi.fn(),
    adminDisableImage: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
}));

test("imagem em download mostra há quanto tempo começou e o progresso bruto, não só 'Baixando' parado", async () => {
  const dezMinutosAtras = new Date(Date.now() - 10 * 60 * 1000).toISOString().replace("T", " ").slice(0, 19);
  api.adminListImages.mockResolvedValue([
    {
      id: 1,
      display_name: "Ubuntu KDE",
      repository: "lscr.io/linuxserver/webtop",
      tag: "ubuntu-kde",
      enabled: true,
      pull_state: "pulling",
      pull_progress: "[====>    ] 1.8GB/7.2GB",
      pull_error: null,
      created_at: dezMinutosAtras,
    },
  ]);

  render(<ImagesPanel />);

  expect(await screen.findByText("Baixando")).toBeInTheDocument();
  expect(await screen.findByText(/há 10 minutos/)).toBeInTheDocument();
  expect(screen.getByText(/1\.8GB\/7\.2GB/)).toBeInTheDocument();
});

test("imagem pronta não mostra progresso nem tempo decorrido", async () => {
  api.adminListImages.mockResolvedValue([
    {
      id: 1,
      display_name: "Webtop",
      repository: "lscr.io/linuxserver/webtop",
      tag: "latest",
      enabled: true,
      pull_state: "ready",
      pull_progress: null,
      pull_error: null,
      created_at: "2024-01-01 00:00:00",
    },
  ]);

  render(<ImagesPanel />);

  expect(await screen.findByText("Pronta")).toBeInTheDocument();
  expect(screen.queryByText(/há .* minuto/)).not.toBeInTheDocument();
});

test("imagem em falha mostra a mensagem de erro", async () => {
  api.adminListImages.mockResolvedValue([
    {
      id: 1,
      display_name: "Webtop",
      repository: "lscr.io/linuxserver/webtop",
      tag: "latest",
      enabled: true,
      pull_state: "failed",
      pull_progress: null,
      pull_error: "registro indisponível",
      created_at: "2024-01-01 00:00:00",
    },
  ]);

  render(<ImagesPanel />);

  expect(await screen.findByText("registro indisponível")).toBeInTheDocument();
});
