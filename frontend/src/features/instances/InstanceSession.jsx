import { useEffect, useRef, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";

const GENERIC_UNAVAILABLE_MESSAGE = "Não foi possível conectar a esta sessão agora.";
const RETRY_INTERVAL_MS = 3000;
const MAX_RETRIES = 20; // ~1 minuto tentando, mesma ordem de grandeza do ciclo do reaper
const TTYD_REFIT_POLL_MS = 100;
const TTYD_REFIT_MAX_WAIT_MS = 5000;

/**
 * Refaz o ajuste do terminal ttyd embutido depois que o iframe carrega.
 *
 * O primeiro ajuste do cliente ttyd acontece antes de as métricas de célula
 * do xterm estarem corretas (o atlas de caracteres mede a fonte pouco depois
 * da abertura): o terminal nasce com menos colunas que o espaço disponível e
 * sobra uma faixa morta à direita da sessão.
 *
 * Um único refit não basta — cedo demais, ele mede com a métrica errada
 * igual ao fit interno (aqui medido: fit cedo => mesmas 154 colunas). Por
 * isso o refit é repetido a cada pulso e só para quando dois pulsos
 * seguidos propõem o mesmo tamanho (cols×rows estável = métrica assentada).
 * Cada fit que muda o tamanho informa o pty; o TUI do agente redesenha a
 * cada SIGWINCH, como já faz num resize de janela.
 *
 * Na mesma janela, troca o overflow do viewport do xterm de "scroll" (que
 * desenha a barra lateral sempre, mesmo sem histórico — a barra fantasma à
 * direita) para "auto", e atualiza a largura de barra que o xterm cachou no
 * construtor do viewport (API privada do xterm, guardada por try/catch: se
 * os internos mudarem entre versões, a sessão segue com o fit interno).
 *
 * No webtop (Selkies) não existe `window.term` — nada é feito e a espera se
 * encerra sozinha no limite de tentativas. Devolve uma função que cancela a
 * espera (para o unmount do iframe).
 */
export function refitEmbeddedTerminal(contentWindow) {
  if (!contentWindow) return () => {};
  let waited = 0;
  let previousSize = null;
  let stablePulses = 0;
  const timer = setInterval(() => {
    let settled = false;
    try {
      const term = contentWindow.term;
      if (term) {
        const viewport = contentWindow.document.querySelector(".xterm-viewport");
        if (viewport) viewport.style.overflowY = "auto";
        const coreViewport = term._core?.viewport;
        const viewportElement = coreViewport?._viewportElement;
        if (coreViewport && viewportElement) {
          coreViewport._scrollBarWidth = Math.max(0, viewportElement.offsetWidth - viewportElement.clientWidth);
        }
        term.fit();
        const size = `${term.cols}x${term.rows}`;
        stablePulses = size === previousSize ? stablePulses + 1 : 0;
        previousSize = size;
        settled = stablePulses >= 2;
      }
    } catch {
      settled = true; // internos mudaram? não insistir: o fit interno do ttyd já rodou
    }
    waited += TTYD_REFIT_POLL_MS;
    if (settled || waited >= TTYD_REFIT_MAX_WAIT_MS) clearInterval(timer);
  }, TTYD_REFIT_POLL_MS);
  return () => clearInterval(timer);
}

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
 *
 * A checagem se repete enquanto não disponível: o container entra em
 * "em execução" assim que o processo começa, bem antes do servidor interno
 * (Selkies) aceitar conexões — sem repetir, o usuário ficaria preso num
 * aviso de erro que se resolveria sozinho poucos segundos depois.
 */
export default function InstanceSession({ instanceId }) {
  const [status, setStatus] = useState("checking"); // checking | ready | unavailable
  const [message, setMessage] = useState(GENERIC_UNAVAILABLE_MESSAGE);
  const cancelRefitRef = useRef(null);

  useEffect(
    () => () => {
      cancelRefitRef.current?.();
    },
    []
  );

  // A carga do iframe é o gatilho para refazer o ajuste do terminal ttyd
  // (ver refitEmbeddedTerminal): o fit interno dele já rodou com métricas
  // erradas nesse ponto, e só refit ao vivo corrige a largura.
  function handleFrameLoad(event) {
    cancelRefitRef.current?.();
    cancelRefitRef.current = refitEmbeddedTerminal(event.currentTarget.contentWindow);
  }

  useEffect(() => {
    let cancelled = false;
    let timeoutId;
    let attempt = 0;

    async function check() {
      let ready = false;
      try {
        const resp = await fetch(`/i/${instanceId}/`, { credentials: "include" });
        if (cancelled) return;
        if (resp.ok) {
          setStatus("ready");
          ready = true;
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
      } catch {
        if (!cancelled) {
          setMessage(GENERIC_UNAVAILABLE_MESSAGE);
          setStatus("unavailable");
        }
      } finally {
        attempt += 1;
        if (!cancelled && !ready && attempt < MAX_RETRIES) {
          timeoutId = setTimeout(check, RETRY_INTERVAL_MS);
        }
      }
    }

    setStatus("checking");
    check();

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
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

  // O parâmetro de dimensionamento (`?resize=scale`) é honrado pelo Selkies
  // (webtop) para acompanhar a área disponível; o cliente do ttyd 1.7.7 o
  // ignora (ele faz fit próprio — corrigido pelo refitEmbeddedTerminal após
  // a carga). Quando o conteúdo ignora o parâmetro, a caixa externa
  // centralizada com o fundo do tema ativo evita a aparência de faixa morta
  // (ver session-view spec — "fundo coerente com o tema ativo").
  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: "background.default",
      }}
    >
      <Box
        component="iframe"
        title={`Sessão da instância ${instanceId}`}
        src={`/i/${instanceId}/?resize=scale`}
        onLoad={handleFrameLoad}
        sx={{ width: "100%", height: "100%", border: 0, display: "block" }}
      />
    </Box>
  );
}
