import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { ADMIN_SECTIONS } from "../features/admin/adminSections";
import AdminPage from "./AdminPage";
import AdminSectionPage from "./AdminSectionPage";

vi.mock("../features/admin/UsersPanel", () => ({ default: () => <div>painel-usuarios</div> }));
vi.mock("../features/admin/GroupsPanel", () => ({ default: () => <div>painel-grupos</div> }));
vi.mock("../features/admin/ImagesPanel", () => ({ default: () => <div>painel-catalogo</div> }));
vi.mock("../features/admin/AgentsMdPanel", () => ({ default: () => <div>painel-agents-md</div> }));
vi.mock("../features/admin/SkillsPanel", () => ({ default: () => <div>painel-skills</div> }));
vi.mock("../features/admin/McpServersPanel", () => ({ default: () => <div>painel-mcp</div> }));
vi.mock("../features/admin/AccessPanel", () => ({ default: () => <div>painel-acessos</div> }));
vi.mock("../features/admin/UsageMetricsPanel", () => ({ default: () => <div>painel-metricas</div> }));

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin" element={<AdminPage />}>
          <Route index element={<AdminSectionPage title={ADMIN_SECTIONS[0].label} Panel={ADMIN_SECTIONS[0].Panel} />} />
          {ADMIN_SECTIONS.map(({ path: sectionPath, label, Panel }) => (
            <Route key={sectionPath} path={sectionPath} element={<AdminSectionPage title={label} Panel={Panel} />} />
          ))}
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

test("/admin sem seção mostra a seção de usuários por padrão", () => {
  renderAt("/admin");

  expect(screen.getByRole("heading", { name: "Usuários" })).toBeInTheDocument();
  expect(screen.getByText("painel-usuarios")).toBeInTheDocument();
});

test("endereço da seção de MCP mostra o título e o painel correspondente", () => {
  renderAt("/admin/mcp");

  expect(screen.getByRole("heading", { name: "MCP" })).toBeInTheDocument();
  expect(screen.getByText("painel-mcp")).toBeInTheDocument();
  expect(screen.queryByText("painel-usuarios")).not.toBeInTheDocument();
});

test("recarregar no endereço de uma seção mantém essa seção (endereço é a fonte da verdade)", () => {
  const { unmount } = renderAt("/admin/grupos");
  expect(screen.getByRole("heading", { name: "Grupos" })).toBeInTheDocument();
  unmount();

  // simula o recarregamento: novo mount no mesmo endereço, sem estado anterior
  renderAt("/admin/grupos");
  expect(screen.getByRole("heading", { name: "Grupos" })).toBeInTheDocument();
  expect(screen.getByText("painel-grupos")).toBeInTheDocument();
});
