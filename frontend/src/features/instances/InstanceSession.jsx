import { useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";

const GENERIC_UNAVAILABLE_MESSAGE = "Não foi possível conectar a esta sessão agora.";

/**
 * Embute a sessão de desktop num iframe same-origin. O caminho é relativo
 * à própria origem do portal (`/i/<id>/`), nunca um endereço de container —
 * é isso que permite embutir sem relaxar o CSP padrão do Selkies
 * (`frame-ancestors 'self'`), ver design.md D1.
 *
 * Antes de montar o iframe, confirma que a sessão responde: quando o
 * encaminhamento recusa (instância parada, indisponível etc.), o corpo da
 * resposta é um JSON de erro — carregá-lo direto como documento do iframe
 * mostraria esse JSON cru na tela. Em vez disso, essa checagem intercepta o
 * erro e mostra um aviso formatado no lugar do iframe.
 */
export default function InstanceSession({ instanceId }) {
  const [status, setStatus] = useState("checking"); // checking | ready | unavailable
  const [message, setMessage] = useState(GENERIC_UNAVAILABLE_MESSAGE);

  useEffect(() => {
    let cancelled = false;
    setStatus("checking");

    fetch(`/i/${instanceId}/`, { credentials: "include" })
      .then(async (resp) => {
        if (cancelled) return;
        if (resp.ok) {
          setStatus("ready");
          return;
        }
        let detail = GENERIC_UNAVAILABLE_MESSAGE;
        try {
          const data = await resp.json();
          if (data?.detail) detail = data.detail;
        } catch {
          // corpo não era JSON (ex.: página de erro do próprio container); mantém a mensagem padrão
        }
        setMessage(detail);
        setStatus("unavailable");
      })
      .catch(() => {
        if (!cancelled) {
          setMessage(GENERIC_UNAVAILABLE_MESSAGE);
          setStatus("unavailable");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [instanceId]);

  if (status === "checking") {
    return (
      <Box sx={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  if (status === "unavailable") {
    return (
      <Box sx={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", p: 2 }}>
        <Alert severity="warning" sx={{ width: "100%" }}>
          {message}
        </Alert>
      </Box>
    );
  }

  return (
    <Box
      component="iframe"
      title={`Sessão da instância ${instanceId}`}
      src={`/i/${instanceId}/`}
      sx={{ width: "100%", height: "100%", border: 0, display: "block" }}
    />
  );
}
