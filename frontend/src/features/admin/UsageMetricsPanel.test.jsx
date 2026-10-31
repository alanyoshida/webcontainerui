import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { api } from "../../api/client";
import UsageMetricsPanel, { formatDuration } from "./UsageMetricsPanel";

vi.mock("../../api/client", () => ({
  api: {
    adminUsageLive: vi.fn(),
    adminUsageRuns: vi.fn(),
    adminUsageSummary: vi.fn(),
  },
}));

// O gráfico real depende de ResizeObserver, que o jsdom não implementa;
// o conteúdo da série já é coberto pelos testes de `daily_series` no
// backend, então aqui só interessa que o painel tente renderizá-lo.
vi.mock("@mui/x-charts/LineChart", () => ({
  LineChart: ({ series }) => <div data-testid="line-chart">{series[0].data.join(",")}</div>,
}));

function liveRow(overrides = {}) {
  return {
    instance_id: "inst-1",
    user_id: 1,
    user_email: "ana@exemplo.test",
    image_id: 7,
    image_display_name: "Webtop",
    image_repository: "lscr.io/linuxserver/webtop",
    image_tag: "latest",
    started_at: "2024-06-10 10:00:00",
    duration_seconds: 5400,
    ...overrides,
  };
}

function runRow(overrides = {}) {
  return {
    id: 1,
    instance_id: "inst-1",
    user_id: 1,
    user_email: "ana@exemplo.test",
    image_id: 7,
    image_display_name: "Webtop",
    image_repository: "lscr.io/linuxserver/webtop",
    image_tag: "latest",
    started_at: "2024-06-10 10:00:00",
    ended_at: "2024-06-10 12:00:00",
    ended_reason: "user_stop",
    duration_seconds: 7200,
    ...overrides,
  };
}

function emptySummary(overrides = {}) {
  return {
    by_user: [],
    by_group: [],
    image_ranking: [],
    reason_breakdown: [],
    daily_series: [{ date: "2024-06-10", count: 1 }],
    peak_concurrency: 1,
    ...overrides,
  };
}

beforeEach(() => {
  api.adminUsageLive.mockResolvedValue([]);
  api.adminUsageRuns.mockResolvedValue({ items: [], total: 0 });
  api.adminUsageSummary.mockResolvedValue(emptySummary());
});

test("formatDuration converte segundos em texto legível", () => {
  expect(formatDuration(90)).toBe("2 min");
  expect(formatDuration(5400)).toBe("1h 30min");
});

test("mostra instâncias em execução com usuário, imagem e duração", async () => {
  api.adminUsageLive.mockResolvedValue([liveRow()]);

  render(<UsageMetricsPanel />);

  expect(await screen.findByText("ana@exemplo.test")).toBeInTheDocument();
  expect(screen.getByText("Webtop")).toBeInTheDocument();
  expect(screen.getByText("1h 30min")).toBeInTheDocument();
});

test("mensagem de nenhuma instância em execução quando a lista vem vazia", async () => {
  render(<UsageMetricsPanel />);

  expect(await screen.findByText("Nenhuma instância em execução no momento.")).toBeInTheDocument();
});

test("renderiza uma página do histórico e permite navegar entre páginas", async () => {
  api.adminUsageRuns.mockImplementation((limit, offset) =>
    Promise.resolve(
      offset === 0
        ? { items: [runRow({ id: 1 })], total: 25 }
        : { items: [runRow({ id: 2, user_email: "bia@exemplo.test" })], total: 25 }
    )
  );
  const user = userEvent.setup();

  render(<UsageMetricsPanel />);

  expect(await screen.findByText("ana@exemplo.test")).toBeInTheDocument();
  expect(screen.getByText("Parada pelo usuário")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Go to page 2" }));

  expect(await screen.findByText("bia@exemplo.test")).toBeInTheDocument();
  expect(api.adminUsageRuns).toHaveBeenCalledWith(20, 20);
});

test("renderiza os agregados a partir do payload de resumo", async () => {
  api.adminUsageSummary.mockResolvedValue(
    emptySummary({
      by_user: [{ user_id: 1, email: "ana@exemplo.test", seconds: 3600 }],
      by_group: [{ group_id: 1, name: "equipe", seconds: 7200 }],
      image_ranking: [
        { image_id: 7, display_name: "Webtop", repository: "r", tag: "t", run_count: 3, seconds: 10800 },
      ],
      reason_breakdown: [{ reason: "idle_timeout", count: 2 }],
      peak_concurrency: 4,
    })
  );

  render(<UsageMetricsPanel />);

  expect(await screen.findByText("1.0")).toBeInTheDocument(); // horas por usuário
  expect(screen.getByText("equipe")).toBeInTheDocument();
  expect(screen.getByText("2.0")).toBeInTheDocument(); // horas por grupo
  expect(screen.getByText("Webtop")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument(); // execuções da imagem
  expect(screen.getByText("Ociosidade: 2")).toBeInTheDocument();
  expect(screen.getByText(/Pico de instâncias simultâneas no período: 4/)).toBeInTheDocument();
  expect(screen.getByTestId("line-chart")).toHaveTextContent("1");
});
