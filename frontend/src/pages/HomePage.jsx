import { useEffect, useState } from "react";
import Container from "@mui/material/Container";
import Stack from "@mui/material/Stack";
import { api } from "../api/client";
import CatalogSection from "../features/catalog/CatalogSection";
import InstanceSessionView from "../features/instances/InstanceSessionView";
import InstancesSection from "../features/instances/InstancesSection";
import RunningNowCard from "../features/instances/RunningNowCard";
import { useInstances } from "../features/instances/useInstances";

export default function HomePage() {
  const { instances, loading, error, create, stop, update, remove } = useInstances();
  const [openInstanceId, setOpenInstanceId] = useState(null);
  const [idleTimeoutMinutes, setIdleTimeoutMinutes] = useState(null);

  useEffect(() => {
    api
      .getPublicConfig()
      .then((config) => setIdleTimeoutMinutes(config.idle_timeout_minutes))
      .catch(() => setIdleTimeoutMinutes(null));
  }, []);

  const openInstance = openInstanceId ? instances.find((i) => i.id === openInstanceId) : null;

  // A instância aberta pode sumir da lista por outro caminho (ex.: excluída
  // em outra aba, ou o polling de useInstances traz uma lista sem ela) —
  // nesse caso não há mais o que mostrar na visão dedicada, então volta
  // sozinho para a listagem em vez de deixar uma visão "órfã" na tela.
  useEffect(() => {
    if (openInstanceId && !loading && !openInstance) {
      setOpenInstanceId(null);
    }
  }, [openInstanceId, openInstance, loading]);

  return (
    <Container maxWidth={openInstance ? "xl" : "lg"} sx={{ py: 4 }}>
      {openInstance ? (
        <InstanceSessionView
          instance={openInstance}
          idleTimeoutMinutes={idleTimeoutMinutes}
          onBack={() => setOpenInstanceId(null)}
          onStop={stop}
          onDelete={remove}
          onUpdate={update}
        />
      ) : (
        <Stack spacing={4}>
          {!loading && !error && <RunningNowCard instances={instances} onOpenSession={setOpenInstanceId} />}
          <CatalogSection onStart={create} />
          <InstancesSection
            instances={instances}
            loading={loading}
            error={error}
            onOpenSession={setOpenInstanceId}
            onStart={create}
            onStop={stop}
            onDelete={remove}
            onUpdate={update}
          />
        </Stack>
      )}
    </Container>
  );
}
