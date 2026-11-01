import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { api, ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import ConfirmDialog from "../../components/ConfirmDialog";

export default function UsersPanel() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [error, setError] = useState("");
  const [disableTarget, setDisableTarget] = useState(null);

  function reload() {
    api.adminListUsers().then(setUsers).catch(() => {});
  }

  useEffect(reload, []);

  async function handleCreate(event) {
    event.preventDefault();
    setError("");
    try {
      await api.adminCreateUser(email, password, isAdmin);
      setEmail("");
      setPassword("");
      setIsAdmin(false);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível criar o usuário.");
    }
  }

  async function handleDisableConfirmed() {
    setError("");
    try {
      await api.adminDisableUser(disableTarget.id);
      setDisableTarget(null);
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Não foi possível desabilitar a conta.");
    }
  }

  return (
    <Stack spacing={3}>
      <Box component="form" onSubmit={handleCreate}>
        <Typography variant="h6" gutterBottom>
          Nova conta
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
          <TextField label="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required size="small" />
          <TextField label="Senha inicial" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required size="small" />
          <FormControlLabel
            control={<Checkbox checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />}
            label="Administrador"
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
              <TableCell>E-mail</TableCell>
              <TableCell>Papel</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Ações</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((user) => (
              <TableRow key={user.id}>
                <TableCell>{user.email}</TableCell>
                <TableCell>{user.is_admin ? "Administrador" : "Usuário"}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    label={user.disabled ? "Desabilitado" : "Ativo"}
                    color={user.disabled ? "default" : "success"}
                  />
                </TableCell>
                <TableCell align="right">
                  {!user.disabled && user.id !== currentUser?.id && (
                    <Button size="small" color="error" onClick={() => setDisableTarget(user)}>
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
        title={`Desabilitar ${disableTarget?.email}?`}
        description={`A conta ${disableTarget?.email} perde acesso imediatamente; o registro e os dados dela são preservados.`}
        confirmLabel="Desabilitar"
        onCancel={() => setDisableTarget(null)}
        onConfirm={handleDisableConfirmed}
      />
    </Stack>
  );
}
