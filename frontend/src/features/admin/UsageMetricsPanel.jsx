import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Pagination from "@mui/material/Pagination";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { LineChart } from "@mui/x-charts/LineChart";
import { api } from "../../api/client";
import SectionTitle from "../../components/SectionTitle";

const REASON_LABEL = {
  user_stop: "Parada pelo usuário",
  idle_timeout: "Ociosidade",
  reconciled: "Queda externa",
  deleted: "Exclusão",
};

const PAGE_SIZE = 20;
const LIVE_POLL_MS = 5000;

export function formatDuration(seconds) {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes} min`;
  return `${hours}h ${minutes}min`;
}

function formatDateTime(sqliteTimestamp) {
  // Vem do SQLite em UTC sem indicação de fuso ("YYYY-MM-DD HH:MM:SS");
  // sem o "Z", o JS interpretaria como hora local (mesmo ajuste de
  // ImagesPanel.jsx).
  return new Date(sqliteTimestamp.replace(" ", "T") + "Z").toLocaleString("pt-BR");
}

export default function UsageMetricsPanel() {
  const [live, setLive] = useState([]);
  const [runsPage, setRunsPage] = useState({ items: [], total: 0 });
  const [page, setPage] = useState(0);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    function reloadLive() {
      api.adminUsageLive().then(setLive).catch(() => setError("Não foi possível carregar as instâncias em execução."));
    }
    reloadLive();
    const interval = setInterval(reloadLive, LIVE_POLL_MS);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    api.adminUsageRuns(PAGE_SIZE, page * PAGE_SIZE).then(setRunsPage).catch(() => {});
  }, [page]);

  useEffect(() => {
    api.adminUsageSummary().then(setSummary).catch(() => {});
  }, []);

  const pageCount = Math.max(1, Math.ceil(runsPage.total / PAGE_SIZE));

  return (
    <Stack spacing={4}>
      {error && <Alert severity="error">{error}</Alert>}

      <Box>
        <SectionTitle>Rodando agora</SectionTitle>
        {live.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Nenhuma instância em execução no momento.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Usuário</TableCell>
                  <TableCell>Imagem</TableCell>
                  <TableCell>Em execução há</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {live.map((row) => (
                  <TableRow key={row.instance_id}>
                    <TableCell>{row.user_email}</TableCell>
                    <TableCell>{row.image_display_name}</TableCell>
                    <TableCell>{formatDuration(row.duration_seconds)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      <Box>
        <SectionTitle>Histórico (últimos 30 dias)</SectionTitle>
        {runsPage.items.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            Nenhuma execução nos últimos 30 dias.
          </Typography>
        ) : (
          <>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Usuário</TableCell>
                    <TableCell>Imagem</TableCell>
                    <TableCell>Início</TableCell>
                    <TableCell>Fim</TableCell>
                    <TableCell>Duração</TableCell>
                    <TableCell>Motivo</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {runsPage.items.map((run) => (
                    <TableRow key={run.id}>
                      <TableCell>{run.user_email}</TableCell>
                      <TableCell>{run.image_display_name}</TableCell>
                      <TableCell>{formatDateTime(run.started_at)}</TableCell>
                      <TableCell>{run.ended_at ? formatDateTime(run.ended_at) : "em execução"}</TableCell>
                      <TableCell>{formatDuration(run.duration_seconds)}</TableCell>
                      <TableCell>{run.ended_reason ? REASON_LABEL[run.ended_reason] ?? run.ended_reason : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <Pagination
              sx={{ mt: 2 }}
              count={pageCount}
              page={page + 1}
              onChange={(_, value) => setPage(value - 1)}
            />
          </>
        )}
      </Box>

      {summary && (
        <>
          <Box>
            <SectionTitle>Uso diário (últimos 30 dias)</SectionTitle>
            <LineChart
              height={240}
              xAxis={[{ scaleType: "point", data: summary.daily_series.map((point) => point.date) }]}
              series={[{ data: summary.daily_series.map((point) => point.count), label: "Instâncias ativas" }]}
            />
          </Box>

          <Stack direction={{ xs: "column", md: "row" }} spacing={4}>
            <Box sx={{ flex: 1 }}>
              <SectionTitle>Horas por usuário</SectionTitle>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Usuário</TableCell>
                      <TableCell align="right">Horas</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {summary.by_user.map((entry) => (
                      <TableRow key={entry.user_id}>
                        <TableCell>{entry.email}</TableCell>
                        <TableCell align="right">{(entry.seconds / 3600).toFixed(1)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>

            <Box sx={{ flex: 1 }}>
              <SectionTitle>Horas por grupo</SectionTitle>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Grupo</TableCell>
                      <TableCell align="right">Horas</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {summary.by_group.map((entry) => (
                      <TableRow key={entry.group_id}>
                        <TableCell>{entry.name}</TableCell>
                        <TableCell align="right">{(entry.seconds / 3600).toFixed(1)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          </Stack>

          <Stack direction={{ xs: "column", md: "row" }} spacing={4}>
            <Box sx={{ flex: 1 }}>
              <SectionTitle>Imagens mais usadas</SectionTitle>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Imagem</TableCell>
                      <TableCell align="right">Execuções</TableCell>
                      <TableCell align="right">Horas</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {summary.image_ranking.map((entry) => (
                      <TableRow key={entry.image_id}>
                        <TableCell>{entry.display_name}</TableCell>
                        <TableCell align="right">{entry.run_count}</TableCell>
                        <TableCell align="right">{(entry.seconds / 3600).toFixed(1)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>

            <Box sx={{ flex: 1 }}>
              <SectionTitle>Motivo de término</SectionTitle>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {summary.reason_breakdown.map((entry) => (
                  <Chip key={entry.reason} label={`${REASON_LABEL[entry.reason] ?? entry.reason}: ${entry.count}`} />
                ))}
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                Pico de instâncias simultâneas no período: {summary.peak_concurrency}
              </Typography>
            </Box>
          </Stack>
        </>
      )}
    </Stack>
  );
}
