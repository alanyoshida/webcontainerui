import { useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardActions from "@mui/material/CardActions";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import ComputerIcon from "@mui/icons-material/Computer";
import InstanceSession from "./InstanceSession";

const STATE_LABEL = {
  running: "Em execução",
  stopped: "Parada",
  starting: "Iniciando",
  error: "Erro",
};

const STATE_COLOR = {
  running: "success",
  stopped: "default",
  starting: "info",
  error: "error",
};

export default function InstanceCard({
  instance,
  idleTimeoutMinutes,
  sessionOpen,
  onToggleSession,
  onStart,
  onStop,
  onDelete,
}) {
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

  const showSession = sessionOpen && instance.state === "running";

  return (
    <Card variant="outlined" sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Box
        sx={{
          aspectRatio: "16 / 9",
          width: "100%",
          bgcolor: "action.hover",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        {showSession ? (
          <InstanceSession instanceId={instance.id} />
        ) : (
          <ComputerIcon color="disabled" sx={{ fontSize: 48 }} />
        )}
      </Box>

      <CardContent sx={{ flexGrow: 1 }}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {instance.image_display_name}
          </Typography>
          <Chip label={STATE_LABEL[instance.state] ?? instance.state} color={STATE_COLOR[instance.state]} size="small" />
        </Stack>
        <Typography variant="body2" color="text.secondary">
          {instance.image_repository}:{instance.image_tag}
        </Typography>

        {instance.state === "error" && instance.error_message && (
          <Alert severity="error" sx={{ mt: 1 }}>
            {instance.error_message}
          </Alert>
        )}

        {instance.state === "stopped" && (
          <Alert severity="info" sx={{ mt: 1 }}>
            Parada — por você ou por inatividade além de {idleTimeoutMinutes} minutos. Seus arquivos
            continuam salvos; iniciar de novo retoma de onde você deixou.
          </Alert>
        )}
      </CardContent>

      <CardActions>
        {instance.state === "running" && (
          <>
            <Button size="small" onClick={onToggleSession}>
              {sessionOpen ? "Ocultar sessão" : "Abrir sessão"}
            </Button>
            <Button size="small" disabled={busy} onClick={() => run(() => onStop(instance.id))}>
              Parar
            </Button>
          </>
        )}

        {(instance.state === "stopped" || instance.state === "error") && (
          <Button size="small" disabled={busy} onClick={() => run(() => onStart(instance.image_id))}>
            Iniciar
          </Button>
        )}

        <Button size="small" color="error" disabled={busy} onClick={() => setConfirmingDelete(true)}>
          Excluir
        </Button>
      </CardActions>

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
          <Button
            color="error"
            disabled={busy}
            onClick={async () => {
              setConfirmingDelete(false);
              await run(() => onDelete(instance.id));
            }}
          >
            Excluir
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}
