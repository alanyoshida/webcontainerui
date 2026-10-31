# Design

## Context

A sessão é exibida por `InstanceSessionView` (cabeçalho com voltar, parar,
excluir e status) que renderiza `InstanceSession`. `InstanceSession` embute o
proxy da sessão num iframe same-origin e já trata disponibilidade/retry. A área
da sessão fica dentro de um `Box` com `flexGrow: 1`, dentro do layout da
página.

O navegador expõe a Fullscreen API em `Element.requestFullscreen`, com prefixo
`webkit` em implementações antigas. A API exige gesto do usuário (o clique no
botão) e dispara `fullscreenchange` quando o estado muda — inclusive quando o
usuário sai pelo `ESC`.

## Goals / Non-Goals

**Goals:**
- Expandir somente a área da sessão (iframe), sem cabeçalho/controles do portal.
- Funcionar em navegadores sem Fullscreen API, com um modo imersivo via CSS.
- Saída clara por botão, `ESC` e automaticamente ao sair da sessão.
- Manter o teclado utilizável sem clique extra após entrar.

**Non-Goals:**
- Tela cheia da visão inteira (cabeçalho junto) — decidido fora de escopo.
- Botão de tela cheia dentro do iframe/ttyd — o ttyd não oferece esse controle.
- Mudanças no backend, no proxy, no banco ou no container.
- Persistir a preferência de tela cheia entre visitas.

## Decisions

### D1: Tela cheia da área da sessão, não da visão inteira
O elemento alvo é o `Box` que envolve o iframe. A Fullscreen API coloca esse
elemento na camada superior do navegador, então cabeçalho e margens somem sem
precisar de CSS para escondê-los. Alternativa descartada: colocar a visão
inteira em tela cheia, que preservaria os controles mas reduziria o espaço do
terminal.

### D2: API nativa com fallback imersivo
Tenta `requestFullscreen` (ou `webkitRequestFullscreen`). Se a função não
existir ou a promessa rejeitar, ativa o modo imersivo: `position: fixed;
inset: 0; z-index` alto, fundo escuro e `overflow: hidden` no `body`. Nesse
modo, um listener de `keydown` trata `ESC`. Alternativa descartada: mostrar
erro, que deixaria o recurso inutilizável em iOS/Safari antigo.

### D3: Estado sincronizado por `fullscreenchange`
O estado nativo é lido de `document.fullscreenElement` (ou
`webkitFullscreenElement`) e atualizado no evento. Isso evita ficar com o
botão errado quando o usuário sai pelo `ESC` ou por outro caminho do navegador.
O modo imersivo tem estado próprio (`immersive`) e não conflita com o nativo.

### D4: Foco no iframe ao entrar
Após a entrada (nativa ou imersiva), o iframe é focado via
`containerRef.current.querySelector("iframe")`. O iframe é same-origin, então
o foco é permitido. Sem isso, o foco ficaria no botão que sumiu da tela e a
digitação não chegaria ao terminal até um clique.

### D5: Saída automática
A visão da sessão encerra a tela cheia ao desmontar (cleanup), ao clicar em
voltar e quando `instance.state` deixa de ser `running`. No modo imersivo,
também restaura o `overflow` do `body`. A tela cheia nativa é encerrada por
`document.exitFullscreen`/`webkitExitFullscreen`; o `ESC` nativo já é tratado
pelo navegador e chega pelo evento.

### D6: Sem mudança de backend
O botão e o modo imersivo vivem só no frontend. O iframe, a autenticação e o
proxy continuam iguais; nenhum contrato de API muda.

## Risks / Trade-offs

- [Risco] Navegadores móveis recusarem ou não suportarem fullscreen de um
  `div` → [Mitigação] o fallback imersivo cobre o caso; o botão nunca fica
  inerte.
- [Risco] O usuário sair da tela cheia por um caminho não previsto → [Mitigação]
  o estado é derivado do evento `fullscreenchange`, não só do clique.
- [Risco] Perder o foco do terminal ao expandir → [Mitigação] foco explícito no
  iframe logo após a entrada.
- [Trade-off] No modo imersivo as barras do navegador continuam visíveis; é o
  limite do navegador, não uma regressão.

## Migration Plan

Nenhuma migração. A mudança é aditiva e só entra em vigor quando o usuário
aciona o botão; o layout padrão continua o mesmo.

## Open Questions

Nenhuma pendente. A implementação deve ser coberta por testes de componente
para os dois caminhos (nativo e imersivo) e para a saída por `ESC`.
