import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import { api } from "../../api/client";
import InstanceCard from "./InstanceCard";

export default function InstancesSection({ instances, loading, error, onStart, onStop, onDelete }) {
  const [idleTimeoutMinutes, setIdleTimeoutMinutes] = useState(null);

  useEffect(() => {
    api
      .getPublicConfig()
      .then((config) => setIdleTimeoutMinutes(config.idle_timeout_minutes))
      .catch(() => setIdleTimeoutMinutes(null));
  }, []);

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

      {instances.map((instance) => (
        <InstanceCard
          key={instance.id}
          instance={instance}
          idleTimeoutMinutes={idleTimeoutMinutes}
          onStart={onStart}
          onStop={onStop}
          onDelete={onDelete}
        />
      ))}
    </section>
  );
}
