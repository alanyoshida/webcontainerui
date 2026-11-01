import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { api } from "../../api/client";

export default function AccessPanel() {
  const [groups, setGroups] = useState([]);
  const [images, setImages] = useState([]);
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [grantedImages, setGrantedImages] = useState([]);
  const [imageToGrant, setImageToGrant] = useState("");
  const [revokeTarget, setRevokeTarget] = useState(null); // { image }
  const [revokePreviewCount, setRevokePreviewCount] = useState(null);

  useEffect(() => {
    api.adminListGroups().then(setGroups).catch(() => {});
    api.adminListImages().then(setImages).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedGroupId) {
      setGrantedImages([]);
      return;
    }
    api.adminListGroupImages(selectedGroupId).then(setGrantedImages).catch(() => {});
  }, [selectedGroupId]);

  async function reloadGranted() {
    setGrantedImages(await api.adminListGroupImages(selectedGroupId));
  }

  async function handleGrant() {
    if (!imageToGrant) return;
    await api.adminGrantImage(selectedGroupId, imageToGrant);
    setImageToGrant("");
    reloadGranted();
  }

  async function openRevokeDialog(image) {
    setRevokeTarget(image);
    const preview = await api.adminRevokePreview(selectedGroupId, image.id);
    setRevokePreviewCount(preview.affected_instance_count);
  }

  async function confirmRevoke() {
    await api.adminRevokeImage(selectedGroupId, revokeTarget.id, true);
    setRevokeTarget(null);
    setRevokePreviewCount(null);
    reloadGranted();
  }

  const grantedIds = new Set(grantedImages.map((i) => i.id));

  return (
    <Stack spacing={3}>
      <TextField
        select
        label="Grupo"
        size="small"
        value={selectedGroupId}
        onChange={(e) => setSelectedGroupId(e.target.value)}
        sx={{ maxWidth: 320 }}
      >
        {groups.map((g) => (
          <MenuItem key={g.id} value={g.id}>
            {g.name}
          </MenuItem>
        ))}
      </TextField>

      {!selectedGroupId && (
        <Typography variant="body2" color="text.secondary">
          Selecione um grupo para ver e editar as permissões.
        </Typography>
      )}

      {selectedGroupId && (
        <>
          <Stack direction="row" spacing={1}>
            <TextField
              select
              size="small"
              label="Conceder imagem"
              value={imageToGrant}
              onChange={(e) => setImageToGrant(e.target.value)}
              sx={{ flexGrow: 1, maxWidth: 320 }}
            >
              {images
                .filter((i) => !grantedIds.has(i.id))
                .map((i) => (
                  <MenuItem key={i.id} value={i.id}>
                    {i.display_name}
                  </MenuItem>
                ))}
            </TextField>
            <Button onClick={handleGrant}>Conceder</Button>
          </Stack>

          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Imagens concedidas a este grupo
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {grantedImages.map((image) => (
                <Chip
                  key={image.id}
                  label={image.display_name}
                  onDelete={() => openRevokeDialog(image)}
                  deleteIcon={<span aria-hidden>×</span>}
                />
              ))}
              {grantedImages.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  Nenhuma imagem concedida ainda.
                </Typography>
              )}
            </Stack>
          </Box>
        </>
      )}

      <Dialog open={revokeTarget !== null} onClose={() => setRevokeTarget(null)}>
        <DialogTitle>Revogar {revokeTarget?.display_name}?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {revokePreviewCount === null
              ? "Calculando impacto..."
              : revokePreviewCount === 0
                ? "Nenhuma instância em execução será afetada."
                : `${revokePreviewCount} instância(s) em execução serão paradas agora. Os volumes dos usuários são preservados.`}
          </DialogContentText>
          {revokePreviewCount > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Usuários com sessão aberta nessa imagem perderão acesso imediatamente.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRevokeTarget(null)}>Cancelar</Button>
          <Button color="error" disabled={revokePreviewCount === null} onClick={confirmRevoke}>
            Revogar
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
