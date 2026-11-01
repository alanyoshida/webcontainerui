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
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { api, ApiError } from "../../api/client";
import ConfirmDialog from "../../components/ConfirmDialog";

export default function GroupsPanel() {
  const [groups, setGroups] = useState([]);
  const [users, setUsers] = useState([]);
  const [newGroupName, setNewGroupName] = useState("");
  const [error, setError] = useState("");
  const [managingGroup, setManagingGroup] = useState(null);
  const [members, setMembers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteTargetMemberCount, setDeleteTargetMemberCount] = useState(null);

  function reloadGroups() {
    api.adminListGroups().then(setGroups).catch(() => {});
  }

  useEffect(() => {
    reloadGroups();
    api.adminListUsers().then(setUsers).catch(() => {});
  }, []);

  async function handleCreateGroup(event) {
    event.preventDefault();
    setError("");
    try {
      await api.adminCreateGroup(newGroupName);
      setNewGroupName("");
      reloadGroups();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível criar o grupo.");
    }
  }

  async function openDeleteDialog(group) {
    setDeleteTarget(group);
    const groupMembers = await api.adminListMembers(group.id);
    setDeleteTargetMemberCount(groupMembers.length);
  }

  async function confirmDeleteGroup() {
    await api.adminDeleteGroup(deleteTarget.id);
    setDeleteTarget(null);
    setDeleteTargetMemberCount(null);
    reloadGroups();
  }

  async function openManageMembers(group) {
    setManagingGroup(group);
    setMembers(await api.adminListMembers(group.id));
  }

  async function handleAddMember() {
    if (!selectedUserId) return;
    await api.adminAddMember(managingGroup.id, selectedUserId);
    setMembers(await api.adminListMembers(managingGroup.id));
    setSelectedUserId("");
  }

  async function handleRemoveMember(userId) {
    await api.adminRemoveMember(managingGroup.id, userId);
    setMembers(await api.adminListMembers(managingGroup.id));
  }

  const memberIds = new Set(members.map((m) => m.id));

  return (
    <Stack spacing={3}>
      <Box component="form" onSubmit={handleCreateGroup}>
        <Typography variant="h6" gutterBottom>
          Novo grupo
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Stack direction="row" spacing={2}>
          <TextField
            label="Nome do grupo"
            size="small"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            required
          />
          <Button type="submit" variant="contained">
            Criar
          </Button>
        </Stack>
      </Box>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Nome</TableCell>
              <TableCell align="right">Ações</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {groups.map((group) => (
              <TableRow key={group.id}>
                <TableCell>{group.name}</TableCell>
                <TableCell align="right">
                  <Button size="small" onClick={() => openManageMembers(group)}>
                    Membros
                  </Button>
                  <Button size="small" color="error" onClick={() => openDeleteDialog(group)}>
                    Excluir
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={managingGroup !== null} onClose={() => setManagingGroup(null)} fullWidth maxWidth="xs">
        <DialogTitle>Membros de {managingGroup?.name}</DialogTitle>
        <DialogContent>
          <Stack spacing={1} sx={{ mb: 2 }}>
            {members.map((member) => (
              <Stack key={member.id} direction="row" alignItems="center" spacing={1}>
                <Chip label={member.email} onDelete={() => handleRemoveMember(member.id)} />
              </Stack>
            ))}
            {members.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                Nenhum membro ainda.
              </Typography>
            )}
          </Stack>
          <Stack direction="row" spacing={1}>
            <TextField
              select
              size="small"
              label="Adicionar usuário"
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              sx={{ flexGrow: 1 }}
            >
              {users
                .filter((u) => !memberIds.has(u.id))
                .map((u) => (
                  <MenuItem key={u.id} value={u.id}>
                    {u.email}
                  </MenuItem>
                ))}
            </TextField>
            <Button onClick={handleAddMember}>Adicionar</Button>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setManagingGroup(null)}>Fechar</Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        title={`Excluir ${deleteTarget?.name}?`}
        description={
          deleteTargetMemberCount === null
            ? "Calculando impacto..."
            : deleteTargetMemberCount === 0
              ? "Este grupo não tem membros. As contas dos usuários não são afetadas."
              : `Este grupo tem ${deleteTargetMemberCount} membro(s). As contas deles são preservadas; só o grupo e suas concessões de imagem deixam de existir.`
        }
        confirmLabel="Excluir"
        confirmDisabled={deleteTargetMemberCount === null}
        onCancel={() => {
          setDeleteTarget(null);
          setDeleteTargetMemberCount(null);
        }}
        onConfirm={confirmDeleteGroup}
      />
    </Stack>
  );
}
