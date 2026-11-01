import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { ExternalLink } from "lucide-react";
import SectionTitle from "../../components/SectionTitle";

/**
 * Resumo fixo das instâncias em execução, no topo da home (ver design.md
 * D8) — sempre dentro da primeira dobra, sem depender da listagem completa
 * mais abaixo.
 */
export default function RunningNowCard({ instances, onOpenSession }) {
  const running = instances.filter((instance) => instance.state === "running");

  return (
    <Card variant="outlined" component="section" aria-label="Em execução agora">
      <CardContent>
        <SectionTitle component="h2">Em execução agora</SectionTitle>

        {running.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Nenhuma instância em execução agora.
          </Typography>
        ) : (
          <Stack spacing={1}>
            {running.map((instance) => (
              <Stack
                key={instance.id}
                direction="row"
                alignItems="center"
                justifyContent="space-between"
                spacing={2}
              >
                <Typography variant="body2">{instance.image_display_name}</Typography>
                <Button size="small" startIcon={<ExternalLink size={16} />} onClick={() => onOpenSession(instance.id)}>
                  Abrir sessão
                </Button>
              </Stack>
            ))}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}
