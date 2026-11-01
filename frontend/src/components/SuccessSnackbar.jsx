import Alert from "@mui/material/Alert";
import Snackbar from "@mui/material/Snackbar";

/**
 * Confirmação visual de sucesso para alterações de dados no console (ver
 * app-shell spec: "ações que alteram dados confirmam o resultado
 * visivelmente"). Complementa o `Alert severity="error"` já usado nos
 * painéis — sucesso e falha ficam visualmente distintos.
 */
export default function SuccessSnackbar({ message, onClose }) {
  return (
    <Snackbar open={Boolean(message)} autoHideDuration={3000} onClose={onClose}>
      <Alert severity="success" onClose={onClose} sx={{ width: "100%" }}>
        {message}
      </Alert>
    </Snackbar>
  );
}
