import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import InstanceSessionView from "./InstanceSessionView";

// jsdom não implementa a Fullscreen API: sem `requestFullscreen` no
// elemento, o hook cai direto no modo imersivo (ver useFullscreen.js), que é
// o caminho exercitado por estes testes — suficiente para verificar a
// interface, já que ela reage a `isFullscreen` independente do modo.

beforeEach(() => {
  // InstanceSession checa a disponibilidade da sessão via fetch antes de
  // montar o iframe; aqui só interessa que ela resolva OK.
  global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
});

function instance(overrides = {}) {
  return {
    id: "inst-1",
    image_id: 7,
    image_display_name: "Webtop",
    image_repository: "lscr.io/linuxserver/webtop",
    image_tag: "latest",
    state: "running",
    error_message: null,
    ...overrides,
  };
}

test("instância em execução mostra a sessão embutida", async () => {
  render(
    <InstanceSessionView
      instance={instance()}
      idleTimeoutMinutes={30}
      onBack={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(await screen.findByTitle(/Sessão da instância inst-1/)).toBeInTheDocument();
});

test("botão voltar chama onBack", async () => {
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={onBack} onStop={vi.fn()} onDelete={vi.fn()} />
  );

  await user.click(screen.getByRole("button", { name: /voltar/i }));

  expect(onBack).toHaveBeenCalledTimes(1);
});

test("parar chama onStop e permanece na visão (não chama onBack)", async () => {
  const onStop = vi.fn();
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={onBack} onStop={onStop} onDelete={vi.fn()} />
  );

  await user.click(screen.getByRole("button", { name: "Parar" }));

  expect(onStop).toHaveBeenCalledWith("inst-1");
  expect(onBack).not.toHaveBeenCalled();
});

test("excluir pede confirmação e, confirmado, chama onDelete seguido de onBack", async () => {
  const onDelete = vi.fn();
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={onBack} onStop={vi.fn()} onDelete={onDelete} />
  );

  await user.click(screen.getByRole("button", { name: "Excluir" }));
  expect(onDelete).not.toHaveBeenCalled();
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Excluir instância?")).toBeInTheDocument();

  await user.click(within(dialog).getByRole("button", { name: "Excluir" }));

  expect(onDelete).toHaveBeenCalledWith("inst-1");
  expect(onBack).toHaveBeenCalledTimes(1);
});

test("cancelar a exclusão não chama onDelete nem onBack", async () => {
  const onDelete = vi.fn();
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={onBack} onStop={vi.fn()} onDelete={onDelete} />
  );

  await user.click(screen.getByRole("button", { name: "Excluir" }));
  await user.click(screen.getByRole("button", { name: /cancelar/i }));

  expect(onDelete).not.toHaveBeenCalled();
  expect(onBack).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.queryByText("Excluir instância?")).not.toBeInTheDocument());
});

test("instância parada mostra o aviso de parada em vez da sessão, sem botão Parar", () => {
  render(
    <InstanceSessionView
      instance={instance({ state: "stopped" })}
      idleTimeoutMinutes={45}
      onBack={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(screen.getByText(/45 minutos/)).toBeInTheDocument();
  expect(screen.queryByTitle(/Sessão da instância/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Parar" })).not.toBeInTheDocument();
});

test("instância em erro mostra a mensagem de erro em vez da sessão", () => {
  render(
    <InstanceSessionView
      instance={instance({ state: "error", error_message: "docker indisponível" })}
      idleTimeoutMinutes={30}
      onBack={vi.fn()}
      onStop={vi.fn()}
      onDelete={vi.fn()}
    />
  );

  expect(screen.getByText("docker indisponível")).toBeInTheDocument();
  expect(screen.queryByTitle(/Sessão da instância/)).not.toBeInTheDocument();
});

test("botão de tela cheia só aparece com a instância em execução", async () => {
  const { rerender } = render(
    <InstanceSessionView instance={instance({ state: "stopped" })} idleTimeoutMinutes={30} onBack={vi.fn()} onStop={vi.fn()} onDelete={vi.fn()} />
  );
  expect(screen.queryByRole("button", { name: /tela cheia/i })).not.toBeInTheDocument();

  rerender(
    <InstanceSessionView instance={instance({ state: "running" })} idleTimeoutMinutes={30} onBack={vi.fn()} onStop={vi.fn()} onDelete={vi.fn()} />
  );
  expect(screen.getByRole("button", { name: "Tela cheia" })).toBeInTheDocument();
  await screen.findByTitle(/Sessão da instância inst-1/);
});

test("entrar em tela cheia mostra o botão de saída e foca o iframe; sair restaura o layout normal", async () => {
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={vi.fn()} onStop={vi.fn()} onDelete={vi.fn()} />
  );
  const iframe = await screen.findByTitle(/Sessão da instância inst-1/);

  expect(screen.queryByRole("button", { name: /sair da tela cheia/i })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Tela cheia" }));

  const exitButton = await screen.findByRole("button", { name: /sair da tela cheia/i });
  expect(iframe).toHaveFocus();

  await user.click(exitButton);

  expect(screen.queryByRole("button", { name: /sair da tela cheia/i })).not.toBeInTheDocument();
});

test("sai da tela cheia ao clicar em voltar", async () => {
  const onBack = vi.fn();
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={onBack} onStop={vi.fn()} onDelete={vi.fn()} />
  );

  await user.click(screen.getByRole("button", { name: "Tela cheia" }));
  await screen.findByRole("button", { name: /sair da tela cheia/i });

  await user.click(screen.getByRole("button", { name: /voltar/i }));

  expect(onBack).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("button", { name: /sair da tela cheia/i })).not.toBeInTheDocument();
});

test("sai da tela cheia quando a instância deixa de estar em execução", async () => {
  const user = userEvent.setup();
  const { rerender } = render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={vi.fn()} onStop={vi.fn()} onDelete={vi.fn()} />
  );

  await user.click(screen.getByRole("button", { name: "Tela cheia" }));
  await screen.findByRole("button", { name: /sair da tela cheia/i });

  rerender(
    <InstanceSessionView instance={instance({ state: "stopped" })} idleTimeoutMinutes={30} onBack={vi.fn()} onStop={vi.fn()} onDelete={vi.fn()} />
  );

  await waitFor(() =>
    expect(screen.queryByRole("button", { name: /sair da tela cheia/i })).not.toBeInTheDocument()
  );
});

test("entrar em tela cheia foca um campo de teclado dentro do iframe quando ele existe (ex.: terminal via ttyd)", async () => {
  const user = userEvent.setup();
  render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={vi.fn()} onStop={vi.fn()} onDelete={vi.fn()} />
  );
  const iframe = await screen.findByTitle(/Sessão da instância inst-1/);

  // Simula o textarea oculto que o xterm.js (usado pelo ttyd) cria dentro do
  // documento do iframe para capturar o teclado — focar só o <iframe> não é
  // suficiente para a digitação chegar a ele. jsdom não navega de fato para
  // `src`, então o documento interno começa sem <body>; criamos um mínimo.
  const innerDoc = iframe.contentDocument;
  if (!innerDoc.body) {
    innerDoc.open();
    innerDoc.write("<html><body></body></html>");
    innerDoc.close();
  }
  const innerTextarea = innerDoc.createElement("textarea");
  innerDoc.body.appendChild(innerTextarea);

  await user.click(screen.getByRole("button", { name: "Tela cheia" }));
  await screen.findByRole("button", { name: /sair da tela cheia/i });

  expect(iframe.contentDocument.activeElement).toBe(innerTextarea);
});

test("sai da tela cheia ao desmontar a visão", async () => {
  const user = userEvent.setup();
  const { unmount } = render(
    <InstanceSessionView instance={instance()} idleTimeoutMinutes={30} onBack={vi.fn()} onStop={vi.fn()} onDelete={vi.fn()} />
  );

  await user.click(screen.getByRole("button", { name: "Tela cheia" }));
  await screen.findByRole("button", { name: /sair da tela cheia/i });

  expect(() => unmount()).not.toThrow();
  expect(document.body.style.overflow).toBe("");
});
