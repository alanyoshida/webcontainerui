import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { api, ApiError } from "../../api/client";
import SuccessSnackbar from "../../components/SuccessSnackbar";
import { imageCountLabel } from "../../utils/pluralize";

export default function AgentsMdPanel() {
  const [documents, setDocuments] = useState([]);
  const [images, setImages] = useState([]);
  const [editing, setEditing] = useState(null);
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  function reload() {
    api.adminListAgentsMd().then((docs) => setDocuments(docs)).catch(() => {});
    api.adminListImageAgentsMdLinks().then((imgs) => setImages(imgs)).catch(() => {});
  }

  useEffect(() => {
    reload();
  }, []);

  function openCreate() {
    setEditing({ id: null });
    setName("");
    setContent("");
    setError("");
  }

  function openEdit(doc) {
    setEditing({ id: doc.id });
    setName(doc.name);
    setContent(doc.content);
    setError("");
  }

  async function handleSave(event) {
    event.preventDefault();
    setError("");
    try {
      if (editing.id === null) {
        await api.adminCreateAgentsMd({ name, content });
      } else {
        await api.adminUpdateAgentsMd(editing.id, { name, content });
      }
      setEditing(null);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível salvar o documento.");
    }
  }

  async function handleDelete(doc) {
    setError("");
    try {
      await api.adminDeleteAgentsMd(doc.id);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível remover o documento.");
    }
  }

  async function handleLinkChange(imageId, documentId) {
    setError("");
    try {
      const resp = await api.adminSetImageAgentsMd(imageId, documentId);
      if (resp.propagation_failures.length > 0) {
        setError(
          `${resp.propagation_failures.length} instância(s) em execução não puderam ser atualizadas.`
        );
      } else {
        setSuccess("Vínculo salvo.");
      }
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível vincular o documento.");
    }
  }

  return (
    <Stack spacing={3}>
      {error && <Alert severity="error">{error}</Alert>}

      <Box>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h6">Documentos AGENTS.md</Typography>
          <Button variant="contained" onClick={openCreate}>
            Novo documento
          </Button>
        </Stack>
        {documents.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Nenhum documento ainda. Crie um texto e vincule às imagens do catálogo.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Nome</TableCell>
                <TableCell>Imagens vinculadas</TableCell>
                <TableCell align="right">Ações</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {documents.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell>{doc.name}</TableCell>
                  <TableCell>
                    <Chip size="small" label={imageCountLabel(doc.linked_images)} />
                  </TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => openEdit(doc)}>
                      Editar
                    </Button>
                    <Button size="small" color="error" onClick={() => handleDelete(doc)}>
                      Remover
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Box>

      <Box>
        <Typography variant="h6" gutterBottom>
          Vínculo por imagem
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Imagem</TableCell>
              <TableCell>Documento</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {images.map((image) => (
              <TableRow key={image.id}>
                <TableCell>
                  {image.display_name} ({image.repository}:{image.tag})
                </TableCell>
                <TableCell>
                  <TextField
                    select
                    size="small"
                    value={image.document_id ?? ""}
                    onChange={(event) =>
                      handleLinkChange(
                        image.id,
                        event.target.value === "" ? null : Number(event.target.value)
                      )
                    }
                    sx={{ minWidth: 220 }}
                  >
                    <MenuItem value="">Nenhum</MenuItem>
                    {documents.map((doc) => (
                      <MenuItem key={doc.id} value={doc.id}>
                        {doc.name}
                      </MenuItem>
                    ))}
                  </TextField>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>

      <Dialog open={editing !== null} onClose={() => setEditing(null)} fullWidth maxWidth="md">
        <DialogTitle>
          {editing !== null && editing.id === null ? "Novo documento" : "Editar documento"}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nome"
              size="small"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
            <TextField
              label="Conteúdo (Markdown)"
              multiline
              rows={14}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              required
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditing(null)}>Cancelar</Button>
          <Button variant="contained" onClick={handleSave}>
            Salvar
          </Button>
        </DialogActions>
      </Dialog>

      <SuccessSnackbar message={success} onClose={() => setSuccess("")} />
    </Stack>
  );
}
