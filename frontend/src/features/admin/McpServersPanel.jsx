import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControlLabel from "@mui/material/FormControlLabel";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { api, ApiError } from "../../api/client";
import ConfirmDialog from "../../components/ConfirmDialog";
import SuccessSnackbar from "../../components/SuccessSnackbar";
import { imageCountLabel } from "../../utils/pluralize";

// Campos condicionais por transporte (mesma regra de validação do backend:
// stdio exige comando; http/sse exige URL).
const TRANSPORTS = ["stdio", "http", "sse"];

export default function McpServersPanel() {
  const [servers, setServers] = useState([]);
  const [images, setImages] = useState([]);
  const [editing, setEditing] = useState(null);
  const [displayName, setDisplayName] = useState("");
  const [transport, setTransport] = useState("stdio");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [url, setUrl] = useState("");
  const [env, setEnv] = useState("");
  const [headers, setHeaders] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
  const [success, setSuccess] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);

  function reload() {
    api.adminListMcpServers().then((rows) => setServers(rows)).catch(() => {});
    api.adminListImageMcpServers().then((rows) => setImages(rows)).catch(() => {});
  }

  useEffect(() => {
    reload();
  }, []);

  function openCreate() {
    setEditing({ id: null });
    setDisplayName("");
    setTransport("stdio");
    setCommand("");
    setArgs("");
    setUrl("");
    setEnv("");
    setHeaders("");
    setEnabled(true);
    setError("");
  }

  function openEdit(server) {
    setEditing({ id: server.id });
    setDisplayName(server.display_name);
    setTransport(server.transport);
    setCommand(server.command ?? "");
    setArgs(server.args.join(" "));
    setUrl(server.url ?? "");
    setEnv((server.env_keys ?? []).join("\n"));
    setHeaders((server.headers_keys ?? []).join("\n"));
    setEnabled(server.enabled);
    setError("");
  }

  // Pares `CHAVE=valor` (um por linha) -> objeto; linhas sem `=` são
  // ignoradas. Segredos existentes não são reexibidos (o backend só devolve
  // as chaves), então editar sem reenviar o valor preserva o que já há.
  function parseKeyValue(text) {
    const out = {};
    for (const line of text.split("\n")) {
      const index = line.indexOf("=");
      if (index > 0) {
        out[line.slice(0, index).trim()] = line.slice(index + 1);
      }
    }
    return out;
  }

  function buildPayload() {
    const payload = {
      display_name: displayName,
      transport,
      enabled,
    };
    if (transport === "stdio") {
      payload.command = command;
      payload.args = args.split(/\s+/).filter(Boolean);
      const envPairs = parseKeyValue(env);
      if (Object.keys(envPairs).length > 0) {
        payload.env = envPairs;
      }
    } else {
      payload.url = url;
      const headerPairs = parseKeyValue(headers);
      if (Object.keys(headerPairs).length > 0) {
        payload.headers = headerPairs;
      }
    }
    return payload;
  }

  function reportValidationErrors(resp) {
    if (resp.schema_validation_errors && resp.schema_validation_errors.length > 0) {
      setWarning(resp.schema_validation_errors.map((e) => e.error).join(" · "));
    }
  }

  async function handleSave(event) {
    event.preventDefault();
    setError("");
    setWarning("");
    try {
      if (editing.id === null) {
        await api.adminCreateMcpServer(buildPayload());
      } else {
        const resp = await api.adminUpdateMcpServer(editing.id, buildPayload());
        reportValidationErrors(resp);
      }
      setEditing(null);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível salvar o servidor MCP.");
    }
  }

  async function handleDeleteConfirmed() {
    setError("");
    setWarning("");
    try {
      const resp = await api.adminDeleteMcpServer(deleteTarget.id);
      reportValidationErrors(resp);
      setDeleteTarget(null);
      reload();
    } catch (err) {
      setDeleteTarget(null);
      setError(err instanceof ApiError ? err.detail : "Não foi possível remover o servidor MCP.");
    }
  }

  async function handleToggleLink(imageId, serverId, linked) {
    setError("");
    setWarning("");
    try {
      const resp = linked
        ? await api.adminUnlinkMcpServer(imageId, serverId)
        : await api.adminLinkMcpServer(imageId, serverId);
      if (resp.propagation_failures && resp.propagation_failures.length > 0) {
        setError(
          `${resp.propagation_failures.length} instância(s) em execução não puderam ser atualizadas.`
        );
      } else {
        setSuccess("Vínculo salvo.");
      }
      reportValidationErrors(resp);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível alterar o vínculo.");
    }
  }

  function transportLabel(server) {
    return server.transport === "stdio"
      ? server.command
      : server.url;
  }

  return (
    <Stack spacing={3}>
      {error && <Alert severity="error">{error}</Alert>}
      {warning && (
        <Alert severity="warning" data-testid="schema-validation-alert">
          {warning}
        </Alert>
      )}

      <Box>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h6">Biblioteca de servidores MCP</Typography>
          <Button variant="contained" onClick={openCreate}>
            Novo servidor
          </Button>
        </Stack>
        {servers.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Nenhum servidor MCP ainda. Cadastre um (stdio, http ou sse) e vincule às imagens de
            agente.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Nome</TableCell>
                  <TableCell>Transporte</TableCell>
                  <TableCell>Destino</TableCell>
                  <TableCell>Imagens vinculadas</TableCell>
                  <TableCell align="right">Ações</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {servers.map((server) => (
                  <TableRow key={server.id}>
                    <TableCell>{server.display_name}</TableCell>
                    <TableCell>
                      <Chip size="small" label={server.transport} />
                      {!server.enabled && (
                        <Chip size="small" label="desativado" color="default" sx={{ ml: 0.5 }} />
                      )}
                    </TableCell>
                    <TableCell>{transportLabel(server)}</TableCell>
                    <TableCell>
                      <Chip size="small" label={imageCountLabel(server.linked_images)} />
                    </TableCell>
                    <TableCell align="right">
                      <Button size="small" onClick={() => openEdit(server)}>
                        Editar
                      </Button>
                      <Button size="small" color="error" onClick={() => setDeleteTarget(server)}>
                        Remover
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      <Box>
        <Typography variant="h6" gutterBottom>
          Vínculo por imagem
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Vincular, desvincular ou editar propaga na hora para as instâncias em execução — sem
          rebuild. Só imagens de agente de código aparecem aqui.
        </Typography>
        {images.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Nenhuma imagem de agente de código disponível.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Imagem</TableCell>
                  <TableCell>Servidores MCP</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {images.map((image) => (
                  <TableRow key={image.id}>
                    <TableCell>
                      {image.display_name} ({image.repository}:{image.tag})
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" flexWrap="wrap" spacing={0}>
                        {servers.map((server) => {
                          const linked = image.mcp_server_ids.includes(server.id);
                          return (
                            <FormControlLabel
                              key={server.id}
                              control={
                                <Checkbox
                                  size="small"
                                  checked={linked}
                                  onChange={() => handleToggleLink(image.id, server.id, linked)}
                                />
                              }
                              label={server.display_name}
                            />
                          );
                        })}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      <Dialog open={editing !== null} onClose={() => setEditing(null)} fullWidth maxWidth="sm">
        <DialogTitle>
          {editing !== null && editing.id === null ? "Novo servidor MCP" : "Editar servidor MCP"}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Nome de exibição"
              size="small"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              required
            />
            <TextField
              label="Transporte"
              size="small"
              select
              value={transport}
              onChange={(event) => setTransport(event.target.value)}
            >
              {TRANSPORTS.map((t) => (
                <MenuItem key={t} value={t}>
                  {t}
                </MenuItem>
              ))}
            </TextField>
            {transport === "stdio" ? (
              <>
                <TextField
                  label="Comando"
                  size="small"
                  placeholder="ex: npx"
                  value={command}
                  onChange={(event) => setCommand(event.target.value)}
                  required
                />
                <TextField
                  label="Argumentos (separados por espaço)"
                  size="small"
                  placeholder="ex: -y @some/mcp-server"
                  value={args}
                  onChange={(event) => setArgs(event.target.value)}
                />
                <TextField
                  label="Variáveis de ambiente (CHAVE=valor, uma por linha)"
                  size="small"
                  multiline
                  minRows={2}
                  placeholder={"API_KEY=valor"}
                  value={env}
                  onChange={(event) => setEnv(event.target.value)}
                  helperText="Valores já cadastrados não são reexibidos; reenvie para trocar."
                />
              </>
            ) : (
              <>
                <TextField
                  label="URL"
                  size="small"
                  placeholder="ex: https://mcp.exemplo.test/sse"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  required
                />
                <TextField
                  label="Headers (CHAVE=valor, um por linha)"
                  size="small"
                  multiline
                  minRows={2}
                  placeholder={"Authorization=Bearer valor"}
                  value={headers}
                  onChange={(event) => setHeaders(event.target.value)}
                  helperText="Valores já cadastrados não são reexibidos; reenvie para trocar."
                />
              </>
            )}
            <FormControlLabel
              control={
                <Checkbox
                  checked={enabled}
                  onChange={(event) => setEnabled(event.target.checked)}
                />
              }
              label="Ativado"
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

      <ConfirmDialog
        open={deleteTarget !== null}
        title={`Remover ${deleteTarget?.display_name}?`}
        description="O efeito alcança imediatamente as instâncias em execução das imagens vinculadas a este servidor — elas deixam de ter esse servidor configurado."
        confirmLabel="Remover"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirmed}
      />

      <SuccessSnackbar message={success} onClose={() => setSuccess("")} />
    </Stack>
  );
}
