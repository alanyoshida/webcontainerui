# Design

## Context

Hoje `InstancesSection.jsx` desenha um `Grid` de `InstanceCard` (um por
instância); abrir a sessão de uma instância faz o próprio `Grid item`
daquela instância crescer para 80% da largura, com a sessão incorporada
(`InstanceSession.jsx`) dentro de uma caixa 16:9 no topo do cartão —
misturada com os cartões das demais instâncias e com o catálogo acima. O
catálogo (`CatalogSection.jsx`) continua grade de cartões com imagem de capa
quadrada; o usuário confirmou que isso não muda. `HomePage.jsx` só compõe
`CatalogSection` e `InstancesSection` empilhados, sem nenhuma noção de
"visão" — ver proposal.md para o pedido original.

## Goals / Non-Goals

**Goals:**
- Listagem de instâncias em tabela (uma linha por instância, ações alinhadas
  à linha), no mesmo espírito da tabela do catálogo administrativo
  (`ImagesPanel.jsx`).
- Abrir sessão troca o conteúdo central da página para uma visão dedicada,
  sem mudar a URL; um botão volta para a listagem.
- A visão dedicada oferece Parar e Excluir diretamente, sem voltar à
  listagem.

**Non-Goals:**
- Não introduz um estado de pausa novo — "Pausar" do pedido original mapeia
  para a ação "Parar" já existente (ver proposal.md - What Changes).
- Não muda `CatalogSection.jsx` nem seu teste.
- Não adiciona rota própria na URL para a sessão (decisão explícita do
  usuário: troca de visão na mesma página, não navegação).
- Não adiciona ação "Iniciar" dentro da visão dedicada: se a instância para
  enquanto a visão está aberta, a visão mostra o estado parado; retomar a
  sessão é feito voltando à listagem. Mantém o escopo no que foi pedido
  (Parar e Excluir).

## Decisions

### Estado de qual sessão está aberta sobe para HomePage, não mais para InstancesSection

Hoje `openSessionIds` (um `Set`, múltiplas sessões podiam "abrir" ao mesmo
tempo, cada uma no seu cartão) vive em `InstancesSection`. Como só existe uma
visão dedicada por vez — abrir uma substitui a listagem inteira, não um
cartão entre outros — o estado vira um único `openInstanceId` (string ou
`null`) em `HomePage.jsx`, que decide entre renderizar a listagem
(`CatalogSection` + `InstancesSection`) ou `InstanceSessionView`.

`InstancesSection` deixa de controlar abertura/fechamento: recebe
`onOpenSession(instanceId)` e só dispara esse callback quando a ação "Abrir
sessão" é clicada na linha.

### InstanceCard.jsx vira InstanceTableRow.jsx

O conceito de "cartão com caixa de preview 16:9 no topo" não existe mais na
listagem — cada instância é uma linha de tabela. `InstanceTableRow.jsx`
substitui `InstanceCard.jsx`: mesma lógica de diálogo de confirmação de
exclusão e estado `busy` que já existia, sem a caixa de preview nem o toggle
"Abrir/Ocultar sessão" (agora é só uma ação que chama `onOpenSession`, sem
alternar estado local). Colunas: Imagem (nome), Referência, Estado (chip,
mais a legenda de erro/parada como subtexto — mesmo padrão de
`ImagesPanel.jsx` para `pull_error`/`pull_progress`), Ações.

### InstanceSessionView.jsx é um componente novo, não uma variação de InstanceCard

Reaproveita `InstanceSession.jsx` (checagem de disponibilidade + retry +
iframe, ver change anterior) sem alterá-lo — ele já só preenche 100% da
largura/altura do que o pai der. O que muda é o contêiner: em vez da caixa
16:9 fixa de `InstanceCard`, `InstanceSessionView` dá a ele uma área alta
(`height: calc(100vh - <altura do cabeçalho>)`, não proporção fixa), porque
agora é o conteúdo principal da página, não um item de grade dividindo
espaço com outros cartões.

Cabeçalho da visão: nome do template, chip de estado, botão "Voltar"
(chama `onBack`), e as ações Parar/Excluir — mesmos botões e diálogo de
confirmação que existiam em `InstanceCard`, só que no topo da visão em vez
de dentro de um `CardActions`.

### Excluir pela visão da sessão volta para a listagem; Parar não

Depois de `onDelete` bem-sucedido, `InstanceSessionView` chama `onBack()` —
não há mais instância para mostrar. Depois de `onStop`, a visão permanece:
`instances` (via polling já existente de `useInstances`) atualiza o estado
para "parada", e a visão passa a mostrar o aviso de parada no lugar do
iframe — mesmo texto que `InstanceCard` já mostrava
("Parada — por você ou por inatividade...").

### Instância some da lista enquanto a visão está aberta (ex.: excluída por outro motivo)

Se `openInstanceId` não for encontrado em `instances` (ex.: a lista
atualizou e a instância não existe mais), `HomePage` volta sozinho para a
listagem — mesmo efeito de `onBack`, sem exigir um clique a mais.

## Risks / Trade-offs

- [Perder a posição de leitura da listagem ao voltar] → a listagem não tem
  hoje nenhum estado de scroll/filtro para preservar; o componente é
  remontado do zero ao voltar, sem perda perceptível.
- [`InstanceSession` sem limite de proporção pode ficar excessivamente alto
  em telas muito largas e baixas] → usar `calc(100vh - <cabeçalho>)` em vez
  de altura irrestrita, e não um valor de viewport sem teto.
