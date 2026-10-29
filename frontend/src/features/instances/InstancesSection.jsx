import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import { api } from "../../api/client";
import InstanceCard from "./InstanceCard";

export default function InstancesSection({ instances, loading, error, onStart, onStop, onDelete }) {
  const [idleTimeoutMinutes, setIdleTimeoutMinutes] = useState(null);
  // Estado do grid, não do card: o tamanho de cada item (80% da tela quando
  // a sessão está aberta, tamanho normal quando fechada) é decisão do
  // layout, então sobe para quem desenha o Grid em vez de ficar isolado
  // dentro de cada InstanceCard.
  const [openSessionIds, setOpenSessionIds] = useState(() => new Set());

  useEffect(() => {
    api
      .getPublicConfig()
      .then((config) => setIdleTimeoutMinutes(config.idle_timeout_minutes))
      .catch(() => setIdleTimeoutMinutes(null));
  }, []);

  function toggleSession(instanceId) {
    setOpenSessionIds((prev) => {
      const next = new Set(prev);
      if (next.has(instanceId)) {
        next.delete(instanceId);
      } else {
        next.add(instanceId);
      }
      return next;
    });
  }

  return (
    <section aria-label="Suas instâncias">
      <Typography variant="h5" component="h2" gutterBottom>
        Minhas instâncias
      </Typography>

      {loading && <CircularProgress size={24} />}
      {error && <Alert severity="error">{error}</Alert>}

      {!loading && !error && instances.length === 0 && (
        <Alert severity="info">Nenhuma instância ainda. Escolha uma imagem no catálogo para começar.</Alert>
      )}

      <Grid container spacing={2}>
        {instances.map((instance) => {
          // Só conta como "aberta" (e ganha os 80%) se a instância também
          // estiver em execução — parar a instância com a sessão marcada
          // como aberta não deve deixar o card grande e vazio.
          const sessionOpen = openSessionIds.has(instance.id) && instance.state === "running";
          return (
            <Grid
              item
              key={instance.id}
              xs={12}
              sm={sessionOpen ? 12 : 6}
              md={sessionOpen ? 12 : 4}
              sx={sessionOpen ? { width: "80%", flexBasis: "80%", maxWidth: "80%", mx: "auto" } : undefined}
            >
              <InstanceCard
                instance={instance}
                idleTimeoutMinutes={idleTimeoutMinutes}
                sessionOpen={sessionOpen}
                onToggleSession={() => toggleSession(instance.id)}
                onStart={onStart}
                onStop={onStop}
                onDelete={onDelete}
              />
            </Grid>
          );
        })}
      </Grid>
    </section>
  );
}
