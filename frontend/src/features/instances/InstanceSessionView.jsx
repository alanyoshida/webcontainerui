import { useEffect, useRef, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import FullscreenExitIcon from "@mui/icons-material/FullscreenExit";
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
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={handleBack}>
          Voltar
        </Button>
        <Typography variant="h5" component="h2" sx={{ flexGrow: 1 }}>
          {instance.image_display_name}
        </Typography>
        <Chip label={STATE_LABEL[instance.state] ?? instance.state} color={STATE_COLOR[instance.state]} />

        {instance.state === "running" && (
          <Button startIcon={<FullscreenIcon />} onClick={enterFullscreen}>
            Tela cheia
          </Button>
        )}
        {instance.state === "running" && (
          <Button disabled={busy} onClick={() => run(() => onStop(instance.id))}>
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
            startIcon={<FullscreenExitIcon />}
            onClick={exitFullscreen}
            sx={{ position: "absolute", top: 8, right: 8, zIndex: 1 }}
          >
            Sair da tela cheia
          </Button>
        )}
      </Box>

      <Dialog open={confirmingDelete} onClose={() => setConfirmingDelete(false)}>
        <DialogTitle>Excluir instância?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Isto remove o container e o volume de {instance.image_display_name}. Os arquivos salvos
            dentro dessa instância serão perdidos de forma definitiva.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmingDelete(false)}>Cancelar</Button>
          <Button color="error" disabled={busy} onClick={handleDeleteConfirmed}>
            Excluir
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
