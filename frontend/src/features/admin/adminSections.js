import { BarChart3, FileText, LayoutGrid, Plug, Puzzle, ShieldCheck, Users, UsersRound } from "lucide-react";
import AccessPanel from "./AccessPanel";
import AgentsMdPanel from "./AgentsMdPanel";
import GroupsPanel from "./GroupsPanel";
import ImagesPanel from "./ImagesPanel";
import McpServersPanel from "./McpServersPanel";
import SkillsPanel from "./SkillsPanel";
import UsageMetricsPanel from "./UsageMetricsPanel";
import UsersPanel from "./UsersPanel";

/**
 * Seções do console administrativo: cada uma tem endereço próprio sob
 * `/admin` (ver design.md D5). Compartilhado entre as rotas (App.jsx) e o
 * menu "Administração" da TopBar, para as duas fontes nunca divergirem.
 * `group` organiza o menu em IAM / gestão de agentes / operação — ver
 * ADMIN_SECTION_GROUPS.
 */
export const ADMIN_SECTIONS = [
  { path: "usuarios", label: "Usuários", Panel: UsersPanel, group: "iam", Icon: Users },
  { path: "grupos", label: "Grupos", Panel: GroupsPanel, group: "iam", Icon: UsersRound },
  { path: "acessos", label: "Acessos", Panel: AccessPanel, group: "iam", Icon: ShieldCheck },
  { path: "catalogo", label: "Catálogo", Panel: ImagesPanel, group: "agents", Icon: LayoutGrid },
  { path: "agents-md", label: "AGENTS.md", Panel: AgentsMdPanel, group: "agents", Icon: FileText },
  { path: "skills", label: "Skills", Panel: SkillsPanel, group: "agents", Icon: Puzzle },
  { path: "mcp", label: "MCP", Panel: McpServersPanel, group: "agents", Icon: Plug },
  { path: "metricas", label: "Métricas de uso", Panel: UsageMetricsPanel, group: "ops", Icon: BarChart3 },
];

/** Rótulo de subtítulo por grupo, na ordem em que aparecem no menu. */
export const ADMIN_SECTION_GROUPS = {
  iam: "IAM",
  agents: "Gestão de agentes",
  ops: null,
};
