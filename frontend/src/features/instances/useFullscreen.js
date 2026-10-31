import { useCallback, useEffect, useRef, useState } from "react";

const FULLSCREEN_CHANGE_EVENTS = ["fullscreenchange", "webkitfullscreenchange"];

function getFullscreenElement() {
  return document.fullscreenElement ?? document.webkitFullscreenElement ?? null;
}

function requestNativeFullscreen(element) {
  const request = element.requestFullscreen ?? element.webkitRequestFullscreen;
  if (typeof request !== "function") {
    return Promise.reject(new Error("Fullscreen API indisponível"));
  }
  return Promise.resolve(request.call(element));
}

function exitNativeFullscreen() {
  const exit = document.exitFullscreen ?? document.webkitExitFullscreen;
  if (typeof exit !== "function") return Promise.resolve();
  return Promise.resolve(exit.call(document));
}

// Alguns hosts que embutem a página (ex.: um navegador dentro de um app)
// nunca resolvem nem rejeitam `requestFullscreen()` — simplesmente ignoram o
// pedido, deixando a promessa pendurada para sempre. Sem um limite de tempo,
// `enter()` ficaria esperando indefinidamente e o botão pareceria não fazer
// nada. Um recuso explícito ainda chega primeiro quando o host responde.
const NATIVE_FULLSCREEN_TIMEOUT_MS = 500;

function requestNativeFullscreenWithTimeout(element) {
  return Promise.race([
    requestNativeFullscreen(element),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Tempo esgotado aguardando a tela cheia nativa")), NATIVE_FULLSCREEN_TIMEOUT_MS)
    ),
  ]);
}

/**
 * Tela cheia da área apontada por `containerRef`, não da página inteira
 * (design.md D1). Tenta a Fullscreen API nativa; quando ela não existe ou a
 * promessa é recusada, cai num modo imersivo controlado só por estado/CSS
 * (design.md D2). O estado nativo é derivado de `fullscreenchange` para não
 * divergir quando o usuário sai pelo `ESC` ou por outro caminho do
 * navegador (design.md D3).
 */
export function useFullscreen(containerRef) {
  const [mode, setMode] = useState("normal"); // normal | native | immersive

  useEffect(() => {
    function handleChange() {
      const element = getFullscreenElement();
      setMode((current) => {
        if (element && element === containerRef.current) return "native";
        return current === "native" ? "normal" : current;
      });
    }

    FULLSCREEN_CHANGE_EVENTS.forEach((event) => document.addEventListener(event, handleChange));
    return () => {
      FULLSCREEN_CHANGE_EVENTS.forEach((event) => document.removeEventListener(event, handleChange));
    };
  }, [containerRef]);

  // Modo imersivo: sem evento nativo para se apoiar, então o próprio hook
  // trata a saída por ESC e o travamento do scroll da página.
  useEffect(() => {
    if (mode !== "immersive") return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape") setMode("normal");
    }

    document.addEventListener("keydown", handleKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [mode]);

  // Foco no iframe da sessão ao entrar, nativo ou imersivo (design.md D4) —
  // sem isso o foco fica no botão que sumiu e a digitação não chega à sessão.
  // `iframe.focus()` sozinho só foca o <body> do documento interno: alguns
  // clientes (ex.: o xterm.js do ttyd) capturam teclado num elemento próprio
  // (um textarea oculto), que não fica focado por tabela a menos que seja
  // focado diretamente. Quando existe um campo assim no documento same-origin
  // do iframe, foca-o em vez do iframe; senão, foca o iframe mesmo (cobre
  // clientes como o Selkies, que capturam teclado no documento do iframe).
  useEffect(() => {
    if (mode === "normal") return;
    const iframe = containerRef.current?.querySelector("iframe");
    if (!iframe) return;
    let innerTarget = null;
    try {
      innerTarget = iframe.contentDocument?.querySelector(
        "textarea, input, [contenteditable='true']"
      );
    } catch {
      innerTarget = null;
    }
    (innerTarget ?? iframe).focus();
  }, [mode, containerRef]);

  const enter = useCallback(async () => {
    const element = containerRef.current;
    if (!element) return;
    try {
      await requestNativeFullscreenWithTimeout(element);
      setMode("native");
    } catch {
      // Cobre tanto a recusa quanto o tempo esgotado (host que nunca
      // responde) — se o nativo ainda vier a entrar depois, o listener de
      // `fullscreenchange` corrige o estado para "native".
      setMode("immersive");
    }
  }, [containerRef]);

  const exit = useCallback(() => {
    setMode((current) => {
      if (current === "native") exitNativeFullscreen();
      return "normal";
    });
  }, []);

  // Saída de segurança ao desmontar: garante que a página não fique presa em
  // tela cheia nativa nem com o scroll travado pelo modo imersivo.
  const exitRef = useRef(exit);
  exitRef.current = exit;
  useEffect(() => {
    return () => {
      exitRef.current();
    };
  }, []);

  return { mode, isFullscreen: mode !== "normal", enter, exit };
}
