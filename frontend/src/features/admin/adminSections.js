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
 */
export const ADMIN_SECTIONS = [
  { path: "usuarios", label: "Usuários", Panel: UsersPanel },
  { path: "grupos", label: "Grupos", Panel: GroupsPanel },
  { path: "catalogo", label: "Catálogo", Panel: ImagesPanel },
  { path: "agents-md", label: "AGENTS.md", Panel: AgentsMdPanel },
  { path: "skills", label: "Skills", Panel: SkillsPanel },
  { path: "mcp", label: "MCP", Panel: McpServersPanel },
  { path: "acessos", label: "Acessos", Panel: AccessPanel },
  { path: "metricas", label: "Métricas de uso", Panel: UsageMetricsPanel },
];
