import { useState } from "react";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import TableCell from "@mui/material/TableCell";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";

export const STATE_LABEL = {
  running: "Em execução",
  stopped: "Parada",
  starting: "Iniciando",
  error: "Erro",
};

export const STATE_COLOR = {
  running: "success",
  stopped: "default",
  starting: "info",
  error: "error",
};

/**
 * Uma linha por instância na tabela de "Minhas instâncias" (ver
 * InstancesSection.jsx). Substitui o antigo InstanceCard — sem caixa de
 * preview, sem toggle de sessão embutida: "Abrir sessão" só avisa o pai
 * (onOpenSession), que decide trocar para a visão dedicada
 * (InstanceSessionView).
 */
export default function InstanceTableRow({
  instance,
  idleTimeoutMinutes,
  onOpenSession,
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

  return (
    <TableRow>
      <TableCell>{instance.image_display_name}</TableCell>
      <TableCell>
        {instance.image_repository}:{instance.image_tag}
      </TableCell>
      <TableCell>
        <Chip size="small" label={STATE_LABEL[instance.state] ?? instance.state} color={STATE_COLOR[instance.state]} />
        {instance.state === "error" && instance.error_message && (
          <Typography variant="caption" color="error" component="div" sx={{ mt: 0.5 }}>
            {instance.error_message}
          </Typography>
        )}
        {instance.state === "stopped" && (
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
            Por você ou por inatividade além de {idleTimeoutMinutes} minutos. Arquivos continuam salvos.
          </Typography>
        )}
      </TableCell>
      <TableCell align="right">
        {instance.state === "running" && (
          <>
            <Button size="small" onClick={() => onOpenSession(instance.id)}>
              Abrir sessão
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
      </TableCell>
    </TableRow>
  );
}
