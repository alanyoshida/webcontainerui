import { useEffect, useRef, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { ArrowLeft, Maximize, Minimize } from "lucide-react";
import ConfirmDialog from "../../components/ConfirmDialog";
import InstanceSession from "./InstanceSession";
import { STATE_COLOR, STATE_LABEL } from "./InstanceTableRow";
import { useFullscreen } from "./useFullscreen";

/**
 * Visão dedicada de uma sessão aberta: substitui a listagem inteira (ver
 * HomePage.jsx) em vez de disputar espaço com ela como antes. Reaproveita
 * InstanceSession.jsx sem alterá-lo — aqui ele só ganha uma área mais alta
 * em vez da caixa 16:9 fixa que tinha dentro do antigo InstanceCard.
 */
export default function InstanceSessionView({ instance, idleTimeoutMinutes, onBack, onStop, onDelete }) {
  const [confirmingStop, setConfirmingStop] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const sessionAreaRef = useRef(null);
  const { isFullscreen, enter: enterFullscreen, exit: exitFullscreen } = useFullscreen(sessionAreaRef);

  // Sai da tela cheia quando a instância deixa de estar em execução (parada
  // manual, pelo reaper, ou falha) — não há mais sessão para mostrar.
  useEffect(() => {
    if (instance.state !== "running" && isFullscreen) {
      exitFullscreen();
    }
  }, [instance.state, isFullscreen, exitFullscreen]);

  async function run(action) {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  }

  function handleBack() {
    exitFullscreen();
    onBack();
  }

  async function handleDeleteConfirmed() {
    setConfirmingDelete(false);
    await run(() => onDelete(instance.id));
    onBack();
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "calc(100vh - 128px)" }}>
      <Stack direction="row" alignItems="center" flexWrap="wrap" useFlexGap spacing={1} sx={{ mb: 2 }}>
        <Button startIcon={<ArrowLeft size={18} />} onClick={handleBack}>
          Voltar
        </Button>
        <Typography variant="h5" component="h2" noWrap sx={{ flexGrow: 1, minWidth: 0 }}>
          {instance.image_display_name}
        </Typography>
        <Chip label={STATE_LABEL[instance.state] ?? instance.state} color={STATE_COLOR[instance.state]} />

        {instance.state === "running" && (
          <Button startIcon={<Maximize size={18} />} onClick={enterFullscreen}>
            Tela cheia
          </Button>
        )}
        {instance.state === "running" && (
          <Button disabled={busy} onClick={() => setConfirmingStop(true)}>
            Parar
          </Button>
        )}
        <Button color="error" disabled={busy} onClick={() => setConfirmingDelete(true)}>
          Excluir
        </Button>
      </Stack>

      <Box
        ref={sessionAreaRef}
        sx={[
          { flexGrow: 1, minHeight: 0, position: "relative" },
          isFullscreen && {
            position: "fixed",
            inset: 0,
            zIndex: (theme) => theme.zIndex.modal + 1,
            bgcolor: "common.black",
          },
        ]}
      >
        {instance.state === "running" ? (
          <InstanceSession instanceId={instance.id} />
        ) : (
          <Box sx={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", p: 2 }}>
            {instance.state === "error" && instance.error_message ? (
              <Alert severity="error" sx={{ width: "100%", maxWidth: 480 }}>
                {instance.error_message}
              </Alert>
            ) : instance.state === "stopped" ? (
              <Alert severity="info" sx={{ width: "100%", maxWidth: 480 }}>
                Parada — por você ou por inatividade além de {idleTimeoutMinutes} minutos. Seus arquivos
                continuam salvos; iniciar de novo retoma de onde você deixou.
              </Alert>
            ) : (
              <Alert severity="info" sx={{ width: "100%", maxWidth: 480 }}>
                Esta instância não está em execução no momento.
              </Alert>
            )}
          </Box>
        )}

        {isFullscreen && (
          <Button
            variant="contained"
            startIcon={<Minimize size={18} />}
            onClick={exitFullscreen}
            sx={{ position: "absolute", top: 8, right: 8, zIndex: 1 }}
          >
            Sair da tela cheia
          </Button>
        )}
      </Box>

      <ConfirmDialog
        open={confirmingStop}
        title="Parar instância?"
        description="Os processos em execução são interrompidos; os arquivos permanecem salvos."
        confirmLabel="Parar"
        onCancel={() => setConfirmingStop(false)}
        onConfirm={async () => {
          setConfirmingStop(false);
          await run(() => onStop(instance.id));
        }}
      />

      <ConfirmDialog
        open={confirmingDelete}
        title="Excluir instância?"
        description={`Isto remove o container e o volume de ${instance.image_display_name}. Os arquivos salvos dentro dessa instância serão perdidos de forma definitiva.`}
        confirmLabel="Excluir"
        onCancel={() => setConfirmingDelete(false)}
        onConfirm={handleDeleteConfirmed}
      />
    </Box>
  );
}
