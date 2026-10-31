import { useState } from "react";
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
import InstanceSession from "./InstanceSession";
import { STATE_COLOR, STATE_LABEL } from "./InstanceTableRow";

/**
 * Visão dedicada de uma sessão aberta: substitui a listagem inteira (ver
 * HomePage.jsx) em vez de disputar espaço com ela como antes. Reaproveita
 * InstanceSession.jsx sem alterá-lo — aqui ele só ganha uma área mais alta
 * em vez da caixa 16:9 fixa que tinha dentro do antigo InstanceCard.
 */
export default function InstanceSessionView({ instance, idleTimeoutMinutes, onBack, onStop, onDelete }) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteConfirmed() {
    setConfirmingDelete(false);
    await run(() => onDelete(instance.id));
    onBack();
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "calc(100vh - 128px)" }}>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={onBack}>
          Voltar
        </Button>
        <Typography variant="h5" component="h2" sx={{ flexGrow: 1 }}>
          {instance.image_display_name}
        </Typography>
        <Chip label={STATE_LABEL[instance.state] ?? instance.state} color={STATE_COLOR[instance.state]} />

        {instance.state === "running" && (
          <Button disabled={busy} onClick={() => run(() => onStop(instance.id))}>
            Parar
          </Button>
        )}
        <Button color="error" disabled={busy} onClick={() => setConfirmingDelete(true)}>
          Excluir
        </Button>
      </Stack>

      <Box sx={{ flexGrow: 1, minHeight: 0 }}>
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
