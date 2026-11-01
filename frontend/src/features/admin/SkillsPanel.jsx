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
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { api, ApiError } from "../../api/client";
import ConfirmDialog from "../../components/ConfirmDialog";
import SuccessSnackbar from "../../components/SuccessSnackbar";
import { imageCountLabel } from "../../utils/pluralize";

const BUILD_STATE_LABEL = { pulling: "Reconstruindo", ready: "Pronta", failed: "Falhou" };
const BUILD_STATE_COLOR = { pulling: "info", ready: "success", failed: "error" };

export default function SkillsPanel() {
  const [skills, setSkills] = useState([]);
  const [images, setImages] = useState([]);
  const [editing, setEditing] = useState(null);
  const [displayName, setDisplayName] = useState("");
  const [repoOwner, setRepoOwner] = useState("");
  const [repoName, setRepoName] = useState("");
  const [subpath, setSubpath] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [linkTarget, setLinkTarget] = useState(null);

  function reload() {
    api.adminListAgentSkills().then((rows) => setSkills(rows)).catch(() => {});
    api.adminListImageAgentSkills().then((rows) => setImages(rows)).catch(() => {});
  }

  useEffect(() => {
    reload();
    const interval = setInterval(reload, 4000); // acompanha o rebuild em segundo plano
    return () => clearInterval(interval);
  }, []);

  function openCreate() {
    setEditing({ id: null });
    setDisplayName("");
    setRepoOwner("");
    setRepoName("");
    setSubpath("");
    setError("");
  }

  function openEdit(skill) {
    setEditing({ id: skill.id });
    setDisplayName(skill.display_name);
    setRepoOwner(skill.repo_owner);
    setRepoName(skill.repo_name);
    setSubpath(skill.subpath);
    setError("");
  }

  async function handleSave(event) {
    event.preventDefault();
    setError("");
    try {
      if (editing.id === null) {
        await api.adminCreateAgentSkill({
          display_name: displayName,
          repo_owner: repoOwner,
          repo_name: repoName,
          subpath,
        });
      } else {
        await api.adminUpdateAgentSkill(editing.id, {
          display_name: displayName,
          repo_owner: repoOwner,
          repo_name: repoName,
          subpath,
        });
      }
      setEditing(null);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível salvar a skill.");
    }
  }

  async function handleDelete(skill) {
    setError("");
    try {
      await api.adminDeleteAgentSkill(skill.id);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível remover a skill.");
    }
  }

  async function confirmToggleLink() {
    const { imageId, skillId, linked } = linkTarget;
    setError("");
    try {
      if (linked) {
        await api.adminUnlinkAgentSkill(imageId, skillId);
      } else {
        await api.adminLinkAgentSkill(imageId, skillId);
      }
      setLinkTarget(null);
      setSuccess(linked ? "Skill desvinculada; build disparado." : "Skill vinculada; build disparado.");
      reload();
    } catch (err) {
      setLinkTarget(null);
      setError(err instanceof ApiError ? err.detail : "Não foi possível alterar o vínculo.");
    }
  }

  function repoLabel(skill) {
    return skill.subpath ? `${skill.repo_owner}/${skill.repo_name}:${skill.subpath}` : `${skill.repo_owner}/${skill.repo_name}`;
  }

  return (
    <Stack spacing={3}>
      {error && <Alert severity="error">{error}</Alert>}

      <Box>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h6">Biblioteca de skills</Typography>
          <Button variant="contained" onClick={openCreate}>
            Nova skill
          </Button>
        </Stack>
        {skills.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Nenhuma skill ainda. Cadastre uma referência do skills.sh e vincule às imagens de
            agente.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Nome</TableCell>
                <TableCell>Repositório</TableCell>
                <TableCell>Imagens vinculadas</TableCell>
                <TableCell align="right">Ações</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {skills.map((skill) => (
                <TableRow key={skill.id}>
                  <TableCell>{skill.display_name}</TableCell>
                  <TableCell>{repoLabel(skill)}</TableCell>
                  <TableCell>
                    <Chip size="small" label={imageCountLabel(skill.linked_images)} />
                  </TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => openEdit(skill)}>
                      Editar
                    </Button>
                    <Button size="small" color="error" onClick={() => handleDelete(skill)}>
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
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Vincular ou desvincular dispara um novo build da imagem. Só imagens de agente de código
          aparecem aqui.
        </Typography>
        {images.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Nenhuma imagem de agente de código disponível.
          </Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Imagem</TableCell>
                <TableCell>Estado do build</TableCell>
                <TableCell>Skills</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {images.map((image) => {
                const building = image.pull_state === "pulling";
                return (
                <TableRow key={image.id}>
                  <TableCell>
                    {image.display_name} ({image.repository}:{image.tag})
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={BUILD_STATE_LABEL[image.pull_state] ?? image.pull_state}
                      color={BUILD_STATE_COLOR[image.pull_state]}
                    />
                    {image.pull_state === "failed" && image.pull_error && (
                      <Typography variant="caption" color="error" component="div" sx={{ mt: 0.5 }}>
                        {image.pull_error}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" flexWrap="wrap" spacing={0}>
                      {skills.map((skill) => {
                        const linked = image.skill_ids.includes(skill.id);
                        return (
                          <FormControlLabel
                            key={skill.id}
                            control={
                              <Checkbox
                                size="small"
                                checked={linked}
                                disabled={building}
                                onChange={() =>
                                  setLinkTarget({
                                    imageId: image.id,
                                    skillId: skill.id,
                                    linked,
                                    imageDisplayName: image.display_name,
                                    skillDisplayName: skill.display_name,
                                  })
                                }
                              />
                            }
                            label={skill.display_name}
                          />
                        );
                      })}
                    </Stack>
                  </TableCell>
                </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Box>

      <Dialog open={editing !== null} onClose={() => setEditing(null)} fullWidth maxWidth="sm">
        <DialogTitle>
          {editing !== null && editing.id === null ? "Nova skill" : "Editar skill"}
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
              label="Owner do GitHub"
              size="small"
              placeholder="ex: vercel-labs"
              value={repoOwner}
              onChange={(event) => setRepoOwner(event.target.value)}
              required
            />
            <TextField
              label="Repositório"
              size="small"
              placeholder="ex: agent-skills"
              value={repoName}
              onChange={(event) => setRepoName(event.target.value)}
              required
            />
            <TextField
              label="Skill dentro do repositório (opcional)"
              size="small"
              placeholder="ex: vercel-optimize — deixe vazio para instalar todas"
              value={subpath}
              onChange={(event) => setSubpath(event.target.value)}
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
        open={linkTarget !== null}
        title={linkTarget?.linked ? "Desvincular skill?" : "Vincular skill?"}
        description={`Isto dispara um novo build de ${linkTarget?.imageDisplayName} para ${
          linkTarget?.linked ? "remover" : "instalar"
        } a skill ${linkTarget?.skillDisplayName}. O progresso pode ser acompanhado como em qualquer outro build.`}
        confirmLabel={linkTarget?.linked ? "Desvincular" : "Vincular"}
        onCancel={() => setLinkTarget(null)}
        onConfirm={confirmToggleLink}
      />

      <SuccessSnackbar message={success} onClose={() => setSuccess("")} />
    </Stack>
  );
}
