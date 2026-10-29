import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import InstanceSession from "./InstanceSession";

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

  expect(src).toBe("/i/abc-123/");
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
