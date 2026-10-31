# Tasks

## 1. Lógica de tela cheia

- [x] 1.1 Criar `frontend/src/features/instances/useFullscreen.js` com entrada
  nativa (`requestFullscreen`/`webkitRequestFullscreen`), fallback imersivo,
  leitura de `document.fullscreenElement`, sincronização por
  `fullscreenchange`, saída por `ESC` no modo imersivo e limpeza no unmount;
  verificar com testes unitários do hook para os caminhos nativo, fallback e
  saída.
- [x] 1.2 Focar o iframe da sessão após entrar em tela cheia; verificar com
  teste de componente que o iframe recebe foco quando o modo é ativado.

## 2. Interface da sessão

- [x] 2.1 Adicionar o botão “Tela cheia” ao cabeçalho de
  `InstanceSessionView`, visível somente com `instance.state === "running"`;
  verificar com teste de componente que o botão aparece apenas nesse estado.
- [x] 2.2 Aplicar ao container da sessão o estilo de modo ativo
  (`fixed`/`inset`/`z-index`/fundo) e o botão flutuante “Sair da tela cheia”;
  verificar com teste que o botão de saída aparece e o layout normal volta ao
  sair.
- [x] 2.3 Encerrar a tela cheia ao clicar em voltar, ao desmontar a visão e
  quando a instância deixar de estar em execução; verificar com testes de
  componente para cada transição.

## 3. Verificação integrada

- [x] 3.1 Rodar a suíte do frontend (`node frontend/node_modules/vitest/vitest.mjs run --root frontend`)
  e confirmar que todos os testes passam.
- [x] 3.2 Verificar manualmente em `http://localhost:8000`: abrir uma sessão de
  agente, entrar em tela cheia, digitar, sair pelo botão e por `ESC`, e
  confirmar que o layout normal é restaurado; repetir numa sessão webtop.
- [x] 3.3 Rodar a suíte do backend (`pytest`) e confirmar que nada regrediu.

## Workflow follow-up

- Arquivar a change após a revisão.
