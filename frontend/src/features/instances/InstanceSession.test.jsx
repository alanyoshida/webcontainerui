import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import InstanceSession from "./InstanceSession";

beforeEach(() => {
  global.fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
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
