import { useState } from "react";
import Container from "@mui/material/Container";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import AccessPanel from "../features/admin/AccessPanel";
import AgentsMdPanel from "../features/admin/AgentsMdPanel";
import GroupsPanel from "../features/admin/GroupsPanel";
import ImagesPanel from "../features/admin/ImagesPanel";
import SkillsPanel from "../features/admin/SkillsPanel";
import UsageMetricsPanel from "../features/admin/UsageMetricsPanel";
import UsersPanel from "../features/admin/UsersPanel";

const TABS = [
  { label: "Usuários", Panel: UsersPanel },
  { label: "Grupos", Panel: GroupsPanel },
  { label: "Catálogo", Panel: ImagesPanel },
  { label: "AGENTS.md", Panel: AgentsMdPanel },
  { label: "Skills", Panel: SkillsPanel },
  { label: "Acessos", Panel: AccessPanel },
  { label: "Métricas de uso", Panel: UsageMetricsPanel },
];

export default function AdminPage() {
  const [tab, setTab] = useState(0);
  const ActivePanel = TABS[tab].Panel;

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Administração
      </Typography>

      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ mb: 3 }}>
        {TABS.map((t) => (
          <Tab key={t.label} label={t.label} />
        ))}
      </Tabs>

      <ActivePanel />
    </Container>
  );
}
