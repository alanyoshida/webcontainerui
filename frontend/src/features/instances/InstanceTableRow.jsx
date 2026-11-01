import { useState } from "react";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import TableCell from "@mui/material/TableCell";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import ConfirmDialog from "../../components/ConfirmDialog";

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
  const [confirmingStop, setConfirmingStop] = useState(false);
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
            <Button size="small" disabled={busy} onClick={() => setConfirmingStop(true)}>
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
          onConfirm={async () => {
            setConfirmingDelete(false);
            await run(() => onDelete(instance.id));
          }}
        />
      </TableCell>
    </TableRow>
  );
}
