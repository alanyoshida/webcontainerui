import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import { api } from "../../api/client";
import SectionTitle from "../../components/SectionTitle";
import InstanceTableRow from "./InstanceTableRow";

/**
 * Lista "Minhas instâncias" como tabela. Não controla mais qual sessão está
 * aberta — isso virou uma troca de visão de página inteira, decidida por
 * quem usa este componente (ver HomePage.jsx), por isso só repassa
 * onOpenSession para cada linha em vez de guardar esse estado aqui.
 */
export default function InstancesSection({ instances, loading, error, onOpenSession, onStart, onStop, onDelete }) {
  const [idleTimeoutMinutes, setIdleTimeoutMinutes] = useState(null);

  useEffect(() => {
    api
      .getPublicConfig()
      .then((config) => setIdleTimeoutMinutes(config.idle_timeout_minutes))
      .catch(() => setIdleTimeoutMinutes(null));
  }, []);

  return (
    <section aria-label="Suas instâncias">
      <SectionTitle variant="h5" component="h2">
        Minhas instâncias
      </SectionTitle>

      {loading && <CircularProgress size={24} />}
      {error && <Alert severity="error">{error}</Alert>}

      {!loading && !error && instances.length === 0 && (
        <Alert severity="info">Nenhuma instância ainda. Escolha uma imagem no catálogo para começar.</Alert>
      )}

      {!loading && !error && instances.length > 0 && (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Imagem</TableCell>
                <TableCell sx={{ display: { xs: "none", sm: "table-cell" } }}>Referência</TableCell>
                <TableCell>Estado</TableCell>
                <TableCell align="right">Ações</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {instances.map((instance) => (
                <InstanceTableRow
                  key={instance.id}
                  instance={instance}
                  idleTimeoutMinutes={idleTimeoutMinutes}
                  onOpenSession={onOpenSession}
                  onStart={onStart}
                  onStop={onStop}
                  onDelete={onDelete}
                />
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </section>
  );
}
