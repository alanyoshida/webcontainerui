import { useEffect, useRef, useState } from "react";
import Alert from "@mui/material/Alert";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { Ban, Image as ImageIcon, Plus, RefreshCw, Upload } from "lucide-react";
import { api, ApiError } from "../../api/client";
import ConfirmDialog from "../../components/ConfirmDialog";
import { MONO_FONT_FAMILY } from "../../theme";

const STATE_LABEL = { pulling: "Baixando", ready: "Pronta", failed: "Falhou" };
const STATE_COLOR = { pulling: "info", ready: "success", failed: "error" };

function elapsedLabel(createdAt) {
  // created_at vem do SQLite em UTC sem timezone explícito ("YYYY-MM-DD
  // HH:MM:SS"); sem o "Z", o JS interpretaria como hora local e erraria
  // o cálculo — por isso o replace abaixo.
  const started = new Date(createdAt.replace(" ", "T") + "Z");
  const minutes = Math.max(0, Math.round((Date.now() - started.getTime()) / 60000));
  if (minutes < 1) return "há poucos segundos";
  if (minutes === 1) return "há 1 minuto";
  return `há ${minutes} minutos`;
}

export default function ImagesPanel() {
  const [images, setImages] = useState([]);
  const [displayName, setDisplayName] = useState("");
  const [repository, setRepository] = useState("lscr.io/linuxserver/webtop");
  const [tag, setTag] = useState("latest");
  const [error, setError] = useState("");
  const [disableTarget, setDisableTarget] = useState(null);
  const fileInputRef = useRef(null);
  const uploadTargetId = useRef(null);

  function reload() {
    api.adminListImages().then(setImages).catch(() => {});
  }

  useEffect(() => {
    reload();
    const interval = setInterval(reload, 4000); // acompanha o progresso do download
    return () => clearInterval(interval);
  }, []);

  async function handleCreate(event) {
    event.preventDefault();
    setError("");
    try {
      await api.adminCreateImage({ display_name: displayName, repository, tag });
      setDisplayName("");
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível registrar a imagem.");
    }
  }

  async function handleRetry(imageId) {
    await api.adminRetryPull(imageId);
    reload();
  }

  async function handleDisableConfirmed() {
    await api.adminDisableImage(disableTarget.id);
    setDisableTarget(null);
    reload();
  }

  function handleUploadIconClick(imageId) {
    uploadTargetId.current = imageId;
    fileInputRef.current?.click();
  }

  async function handleIconFileSelected(event) {
    const file = event.target.files[0];
    const imageId = uploadTargetId.current;
    event.target.value = "";
    if (!file || !imageId) return;

    setError("");
    try {
      await api.adminUploadImageIcon(imageId, file);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível enviar a imagem de capa.");
    }
  }

  return (
    <Stack spacing={3}>
      <input
        type="file"
        accept="image/*"
        ref={fileInputRef}
        onChange={handleIconFileSelected}
        style={{ display: "none" }}
        data-testid="icon-file-input"
      />
      <Box component="form" onSubmit={handleCreate}>
        <Typography variant="h6" gutterBottom>
          Registrar imagem
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <TextField
            label="Nome de exibição"
            size="small"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
          <TextField
            label="Repositório"
            size="small"
            value={repository}
            onChange={(e) => setRepository(e.target.value)}
            required
          />
          <TextField label="Tag" size="small" value={tag} onChange={(e) => setTag(e.target.value)} required />
          <Button type="submit" variant="contained" startIcon={<Plus size={16} />}>
            Registrar
          </Button>
        </Stack>
      </Box>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Capa</TableCell>
              <TableCell>Imagem</TableCell>
              <TableCell>Referência</TableCell>
              <TableCell>Estado</TableCell>
              <TableCell align="right">Ações</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {images.map((image) => (
              <TableRow key={image.id}>
                <TableCell>
                  <Avatar src={image.icon_url ?? undefined} variant="rounded">
                    {!image.icon_url && <ImageIcon size={20} />}
                  </Avatar>
                </TableCell>
                <TableCell>{image.display_name}</TableCell>
                <TableCell sx={{ fontFamily: MONO_FONT_FAMILY }}>
                  {image.repository}:{image.tag}
                </TableCell>
                <TableCell>
                  <Chip size="small" label={STATE_LABEL[image.pull_state] ?? image.pull_state} color={STATE_COLOR[image.pull_state]} />
                  {!image.enabled && <Chip size="small" label="Desabilitada" sx={{ ml: 1 }} />}
                  {image.pull_state === "pulling" && (
                    <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
                      Iniciado {elapsedLabel(image.created_at)}
                      {image.pull_progress && ` — ${image.pull_progress}`}
                    </Typography>
                  )}
                  {image.pull_state === "failed" && image.pull_error && (
                    <Typography variant="caption" color="error" component="div" sx={{ mt: 0.5 }}>
                      {image.pull_error}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  <Button size="small" startIcon={<Upload size={16} />} onClick={() => handleUploadIconClick(image.id)}>
                    Enviar capa
                  </Button>
                  {image.pull_state === "failed" && (
                    <Button size="small" startIcon={<RefreshCw size={16} />} onClick={() => handleRetry(image.id)}>
                      Tentar de novo
                    </Button>
                  )}
                  {image.enabled && (
                    <Button size="small" color="error" startIcon={<Ban size={16} />} onClick={() => setDisableTarget(image)}>
                      Desabilitar
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <ConfirmDialog
        open={disableTarget !== null}
        title={`Desabilitar ${disableTarget?.display_name}?`}
        description="A entrada deixa de aparecer no catálogo oferecido aos usuários e novas instâncias a partir dela passam a ser recusadas. O registro é preservado."
        confirmLabel="Desabilitar"
        confirmIcon={<Ban size={16} />}
        onCancel={() => setDisableTarget(null)}
        onConfirm={handleDisableConfirmed}
      />
    </Stack>
  );
}
