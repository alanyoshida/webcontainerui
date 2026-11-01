import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import InstanceSession, { refitEmbeddedTerminal } from "./InstanceSession";

beforeEach(() => {
  global.fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

test("o endereço usado é relativo à própria origem, não um host de container", async () => {
  global.fetch.mockResolvedValue(new Response(null, { status: 200 }));

  render(<InstanceSession instanceId="abc-123" />);

  const iframe = await screen.findByTitle(/Sessão da instância abc-123/);
  const src = iframe.getAttribute("src");

  expect(src).toBe("/i/abc-123/?resize=scale");
  expect(src).not.toMatch(/^https?:\/\//); // nunca aponta para outra origem
});

test("sessão indisponível mostra a mensagem do backend em vez do JSON cru", async () => {
  global.fetch.mockResolvedValue(
    new Response(JSON.stringify({ detail: "instância não está em execução" }), {
      status: 409,
      headers: { "Content-Type": "application/json" },
    })
  );

  render(<InstanceSession instanceId="abc-123" />);

  expect(await screen.findByText("instância não está em execução")).toBeInTheDocument();
  expect(screen.queryByTitle(/Sessão da instância/)).not.toBeInTheDocument();
  expect(screen.queryByText(/"detail"/)).not.toBeInTheDocument();
});

test("falha de rede ao checar a sessão mostra mensagem genérica, não quebra", async () => {
  global.fetch.mockRejectedValue(new TypeError("Failed to fetch"));

  render(<InstanceSession instanceId="abc-123" />);

  expect(await screen.findByText("Não foi possível conectar a esta sessão agora.")).toBeInTheDocument();
});

test("resposta de erro sem corpo JSON cai na mensagem genérica", async () => {
  global.fetch.mockResolvedValue(new Response("<html>502</html>", { status: 502 }));

  render(<InstanceSession instanceId="abc-123" />);

  expect(await screen.findByText("Não foi possível conectar a esta sessão agora.")).toBeInTheDocument();
});

test("indisponível no início mas pronta pouco depois: tenta de novo sozinho e mostra o iframe", async () => {
  vi.useFakeTimers();
  global.fetch
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "instância indisponível" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      })
    )
    .mockResolvedValueOnce(new Response(null, { status: 200 }));

  render(<InstanceSession instanceId="abc-123" />);

  await act(async () => {
    await Promise.resolve();
  });
  expect(screen.getByText("instância indisponível")).toBeInTheDocument();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });

  expect(screen.getByTitle(/Sessão da instância abc-123/)).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(2);
});

test("para de tentar depois do limite de tentativas, sem loop infinito", async () => {
  vi.useFakeTimers();
  // mockImplementation (não mockResolvedValue): o corpo de uma Response só
  // pode ser lido uma vez, e aqui o fetch é chamado várias vezes — cada
  // chamada precisa da sua própria instância, senão o .json() das tentativas
  // seguintes falha por corpo já consumido.
  global.fetch.mockImplementation(
    () =>
      new Response(JSON.stringify({ detail: "instância indisponível" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      })
  );

  render(<InstanceSession instanceId="abc-123" />);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000 * 25); // bem além do limite de tentativas
  });

  expect(screen.getByText("instância indisponível")).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(20);
});

function fakeViewportElement(offset, client) {
  return { offsetWidth: offset, clientWidth: client };
}

// Janela falsa com o essencial do lado ttyd: viewport do xterm e o terminal
// com tamanho estável (fit não muda cols/rows a menos que o teste simule).
function fakeTtydWindow({ coreViewport = null, cols = 172, rows = 40 } = {}) {
  const viewport = { style: {} };
  const term = {
    fit: vi.fn(),
    cols,
    rows,
    _core: { viewport: coreViewport },
  };
  const contentWindow = {
    term,
    document: {
      querySelector: vi.fn((selector) => {
        if (selector === ".xterm-viewport") return viewport;
        return null;
      }),
    },
  };
  return { term, viewport, contentWindow };
}

test("refit: com window.term presente, troca overflow, atualiza largura de barra e refaz o fit", () => {
  vi.useFakeTimers();
  const coreViewport = { _viewportElement: fakeViewportElement(123, 108), _scrollBarWidth: 15 };
  // tamanho estável desde o primeiro pulso: encerra após dois fits iguais
  const { term, viewport, contentWindow } = fakeTtydWindow({ coreViewport });

  const cancel = refitEmbeddedTerminal(contentWindow);
  vi.advanceTimersByTime(100);
  vi.advanceTimersByTime(100);
  vi.advanceTimersByTime(100);

  expect(viewport.style.overflowY).toBe("auto");
  expect(coreViewport._scrollBarWidth).toBe(15); // 123 - 108
  expect(term.fit).toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0); // estabilizou e encerrou sozinho
  cancel();
});

test("refit: métricas desatualizadas — repete o fit até o tamanho estabilizar", () => {
  vi.useFakeTimers();
  const coreViewport = { _viewportElement: fakeViewportElement(123, 123), _scrollBarWidth: 15 };
  // dois primeiros fits reproduzem o tamanho errado (154), depois assenta em 172
  const colsPorPulso = [154, 154, 172, 172, 172, 172];
  let pulses = 0;
  const { term, contentWindow } = fakeTtydWindow({ coreViewport });
  term.fit.mockImplementation(() => {
    term.cols = colsPorPulso[Math.min(pulses, colsPorPulso.length - 1)];
    pulses += 1;
  });

  const cancel = refitEmbeddedTerminal(contentWindow);
  // pulso 1: 154 (mudou); pulso 2: 154 (1º estável); pulso 3: 172 (mudou);
  // pulsos 4 e 5: 172 (dois estáveis) => encerra
  vi.advanceTimersByTime(100);
  vi.advanceTimersByTime(100);
  vi.advanceTimersByTime(100);
  vi.advanceTimersByTime(100);
  vi.advanceTimersByTime(100);
  vi.advanceTimersByTime(100);

  expect(pulses).toBe(5);
  expect(term.cols).toBe(172);
  expect(vi.getTimerCount()).toBe(0); // encerrou sozinho ao estabilizar
  cancel();
});

test("refit: term chega depois e a espera se encerra sozinha", () => {
  vi.useFakeTimers();
  let readCount = 0;
  const settled = fakeTtydWindow();
  const contentWindow = {
    document: { querySelector: () => null },
    get term() {
      readCount += 1;
      return readCount >= 3 ? settled.term : undefined;
    },
  };

  refitEmbeddedTerminal(contentWindow);
  vi.advanceTimersByTime(100); // leitura 1 — sem term
  vi.advanceTimersByTime(100); // leitura 2 — sem term
  vi.advanceTimersByTime(100); // leitura 3 — term aparece, 1º fit (mudou)
  vi.advanceTimersByTime(100); // 2º fit (1º estável)
  vi.advanceTimersByTime(100); // 3º fit (2º estável) — encerra aqui
  expect(settled.term.fit).toHaveBeenCalledTimes(3);
  expect(vi.getTimerCount()).toBe(0);
});

test("refit: sem term (webtop/Selkies) espera no máximo o limite e limpa o timer", () => {
  vi.useFakeTimers();
  let reads = 0;
  const contentWindow = {
    document: { querySelector: () => null },
  };
  Object.defineProperty(contentWindow, "term", {
    configurable: true,
    get: () => {
      reads += 1;
      return undefined;
    },
  });

  const cancel = refitEmbeddedTerminal(contentWindow);
  vi.advanceTimersByTime(5000);
  const readsAtLimit = reads;
  vi.advanceTimersByTime(1000);
  expect(reads).toBe(readsAtLimit); // interval já foi limpo no limite
  cancel();
});

test("refit: contentWindow ausente não quebra", () => {
  expect(() => refitEmbeddedTerminal(null)).not.toThrow();
});

test("refit: internals do xterm diferentes da versão esperada não quebram a sessão", () => {
  vi.useFakeTimers();
  const term = { fit: vi.fn() }; // sem _core nem element — nunca "preenche"
  const contentWindow = { term, document: { querySelector: () => null } };

  expect(() => refitEmbeddedTerminal(contentWindow)).not.toThrow();
  vi.advanceTimersByTime(100);
  expect(term.fit).toHaveBeenCalled();
  vi.advanceTimersByTime(5000); // esgota a espera sem quebrar
  expect(vi.getTimerCount()).toBe(0);
});

test("a carga do iframe dispara o refit do terminal embutido", async () => {
  vi.useFakeTimers();
  global.fetch.mockResolvedValue(new Response(null, { status: 200 }));

  render(<InstanceSession instanceId="abc-123" />);
  await act(async () => {
    await Promise.resolve();
  });
  const iframe = screen.getByTitle(/Sessão da instância abc-123/);

  const term = { fit: vi.fn(), _core: { viewport: null } };
  Object.defineProperty(iframe.contentWindow, "term", { configurable: true, value: term });

  fireEvent.load(iframe);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(100);
  });

  expect(term.fit).toHaveBeenCalledTimes(1);
});
