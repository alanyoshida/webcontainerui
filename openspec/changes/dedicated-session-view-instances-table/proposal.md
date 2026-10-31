# Proposal

## Why

Hoje abrir a sessão de uma instância expande o próprio cartão dela dentro da
grade (80% da largura, misturado com os demais cartões parados). Isso deixa a
sessão espremida entre o catálogo e as outras instâncias, e a listagem de
instâncias — hoje em grade de cartões — fica difícil de escanear rapidamente
quando há várias. O pedido é separar as duas preocupações: uma listagem
tabular, compacta, com ações por linha; e uma visão dedicada para a sessão
aberta, que ocupe a área central da página em vez de disputar espaço com a
listagem.

## What Changes

- A listagem de "Minhas instâncias" passa de grade de cartões para uma
  tabela (nome, referência da imagem, estado, ações por linha), no mesmo
  espírito da tabela já usada no catálogo administrativo
  (`ImagesPanel.jsx`). O catálogo de templates (`CatalogSection.jsx`)
  permanece como está — grade de cartões com imagem de capa quadrada e nome.
- Clicar em "Abrir sessão" troca o conteúdo central da página: a listagem
  (catálogo + tabela de instâncias) é substituída pela visão dedicada daquela
  sessão, sem mudar a URL. Um botão "Voltar" retorna à listagem.
- A visão dedicada da sessão aberta ganha os botões **Parar** e **Excluir**
  diretamente nela, sem exigir voltar à listagem para essas ações.
  "Pausar", como usado no pedido original, mapeia para a ação **Parar** já
  existente (para o container, preserva o volume) — não introduz um estado
  de pausa novo, o que contradiria o requisito já registrado em
  `desktop-instances` de que não deve existir estado de pausa.
- Excluir a instância a partir da visão da sessão retorna à listagem após a
  confirmação (não há mais o que mostrar na visão dedicada). Parar a
  instância a partir da visão da sessão mantém o usuário na visão dedicada,
  mostrando o estado "parada" no lugar da sessão incorporada.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `desktop-instances`: a listagem de instâncias passa de grade responsiva de
  cartões para tabela com ações por linha; abrir uma sessão passa a trocar a
  visão central da página (visão dedicada) em vez de expandir o cartão
  dentro da listagem; a visão dedicada da sessão ganha as ações de parar e
  excluir.

## Impact

- Frontend: `frontend/src/features/instances/InstancesSection.jsx` (tabela em
  vez de grade), `frontend/src/features/instances/InstanceCard.jsx`
  (substituído por `InstanceTableRow.jsx`, uma linha de tabela em vez de
  cartão), novo `frontend/src/features/instances/InstanceSessionView.jsx`
  (visão dedicada), `frontend/src/pages/HomePage.jsx` (decide entre mostrar a
  listagem ou a visão dedicada). `InstanceSession.jsx` (embedding do iframe
  com checagem/retry) é reaproveitado sem mudanças internas.
- Sem mudança de backend, sem mudança de API — não é **BREAKING**.
