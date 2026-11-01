import { useState } from "react";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import { X } from "lucide-react";

/**
 * Diálogo de confirmação único para toda ação destrutiva do console (ver
 * design.md D6) — generaliza o padrão já usado em AccessPanel: título,
 * descrição do impacto, confirmação destacada em vermelho, foco inicial no
 * cancelar e estado de busy enquanto a confirmação roda. `confirmIcon` é
 * passado por quem chama, pois varia por ação (parar, excluir, vincular...).
 */
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  confirmIcon,
  confirmDisabled = false,
  onCancel,
  onConfirm,
}) {
  const [busy, setBusy] = useState(false);

  async function handleConfirm() {
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onClose={busy ? undefined : onCancel}>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        {typeof description === "string" ? (
          <DialogContentText>{description}</DialogContentText>
        ) : (
          description
        )}
      </DialogContent>
      <DialogActions>
        <Button autoFocus onClick={onCancel} disabled={busy} startIcon={<X size={16} />}>
          {cancelLabel}
        </Button>
        <Button
          color="error"
          variant="contained"
          disabled={busy || confirmDisabled}
          onClick={handleConfirm}
          startIcon={confirmIcon}
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
