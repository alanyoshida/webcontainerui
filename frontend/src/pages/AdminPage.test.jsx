import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import AdminPage from "./AdminPage";

vi.mock("../features/admin/UsersPanel", () => ({ default: () => <div>painel-usuarios</div> }));
vi.mock("../features/admin/GroupsPanel", () => ({ default: () => <div>painel-grupos</div> }));
vi.mock("../features/admin/ImagesPanel", () => ({ default: () => <div>painel-catalogo</div> }));
vi.mock("../features/admin/AccessPanel", () => ({ default: () => <div>painel-acessos</div> }));
vi.mock("../features/admin/UsageMetricsPanel", () => ({ default: () => <div>painel-metricas</div> }));

test("aba Métricas de uso aparece e troca o painel ativo ao ser clicada", async () => {
  const user = userEvent.setup();
  render(<AdminPage />);

  expect(screen.getByText("painel-usuarios")).toBeInTheDocument();
  expect(screen.queryByText("painel-metricas")).not.toBeInTheDocument();

  await user.click(screen.getByRole("tab", { name: "Métricas de uso" }));

  expect(screen.getByText("painel-metricas")).toBeInTheDocument();
  expect(screen.queryByText("painel-usuarios")).not.toBeInTheDocument();
});
