# Proposal

## Why

Hoje a sessão de uma instância fica presa ao espaço da página, com o cabeçalho e
as margens do portal consumindo área útil. Em agentes de código em CLI — cuja
interface é o próprio terminal — isso reduz bastante o espaço disponível. Falta
uma forma de expandir a área da sessão para a tela inteira sem perder o controle
de sair.

## What Changes

- A visão de uma sessão em execução passa a oferecer um botão de **tela cheia**
  que expande somente a área da sessão (o iframe), escondendo cabeçalho e
  controles do portal.
- A tela cheia usa a Fullscreen API nativa quando disponível e aceita; quando o
  navegador não suporta ou recusa, cai num modo imersivo via CSS que ocupa a
  viewport.
- O usuário sai da tela cheia pelo `ESC` (nativo), por um botão flutuante de
  saída, ou automaticamente ao voltar para a listagem, ao desmontar a sessão ou
  quando a instância deixa de estar em execução.
- O recurso vale para qualquer sessão em execução (agentes e webtop), já que o
  componente de sessão é compartilhado.
- Sem mudança de backend, banco, Docker ou proxy.

## Capabilities

### New Capabilities

- `session-view`: como o portal exibe uma sessão em execução, incluindo a
  possibilidade de expandi-la para tela cheia e as formas de sair desse modo.

### Modified Capabilities

(Nenhuma — o ciclo de vida da instância e o encaminhamento da sessão não mudam.)

## Impact

- `frontend/src/features/instances/InstanceSessionView.jsx`: botão e estado de
  tela cheia, modo imersivo de fallback e sincronização com a Fullscreen API.
- Possível extração de `frontend/src/features/instances/useFullscreen.js` para
  isolar a lógica de fullscreen.
- `frontend/src/features/instances/InstanceSessionView.test.jsx`: testes de
  entrada/saída, fallback, `ESC` e instância não executando.
- Nenhuma dependência nova: usa a Fullscreen API do navegador e ícones já
  disponíveis em `@mui/icons-material`.
