import { useState } from "react";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import TableCell from "@mui/material/TableCell";
import TableRow from "@mui/material/TableRow";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import DeleteIcon from "@mui/icons-material/Delete";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import ConfirmDialog from "../../components/ConfirmDialog";
import { MONO_FONT_FAMILY } from "../../theme";

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
 * (InstanceSessionView). Ações em `IconButton` com `Tooltip` (ver
 * design.md D9) — alvo de toque melhor e cabe em janelas estreitas sem
 * empurrar a coluna de ações para fora da viewport.
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
      <TableCell sx={{ display: { xs: "none", sm: "table-cell" }, fontFamily: MONO_FONT_FAMILY }}>
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
        <Stack direction="row" justifyContent="flex-end">
          {instance.state === "running" && (
            <>
              <Tooltip title="Abrir sessão">
                <IconButton size="small" onClick={() => onOpenSession(instance.id)}>
                  <OpenInNewIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="Parar">
                <IconButton size="small" disabled={busy} onClick={() => setConfirmingStop(true)}>
                  <StopIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </>
          )}

          {(instance.state === "stopped" || instance.state === "error") && (
            <Tooltip title="Iniciar">
              <IconButton size="small" disabled={busy} onClick={() => run(() => onStart(instance.image_id))}>
                <PlayArrowIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}

          <Tooltip title="Excluir">
            <IconButton size="small" color="error" disabled={busy} onClick={() => setConfirmingDelete(true)}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>

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
