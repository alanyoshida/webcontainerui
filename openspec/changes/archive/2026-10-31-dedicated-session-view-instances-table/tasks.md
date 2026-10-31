# Tasks

## 1. Linha de tabela para instância (substitui o cartão)

- [x] 1.1 Criar `frontend/src/features/instances/InstanceTableRow.jsx` a
      partir de `InstanceCard.jsx`: mesma lógica de diálogo de confirmação de
      exclusão e estado `busy`, sem a caixa de preview 16:9 nem o toggle
      "Abrir/Ocultar sessão" — a ação "Abrir sessão" chama `onOpenSession`
      em vez de alternar estado local; verificar com teste novo
      `InstanceTableRow.test.jsx` cobrindo as ações por estado (em execução:
      abrir sessão/parar/excluir; parada ou erro: iniciar/excluir) e o
      diálogo de confirmação de exclusão
- [x] 1.2 Remover `InstanceCard.jsx` e `InstanceCard.test.jsx` (substituídos
      por 1.1); verificar que nada mais importa esses arquivos
      (`grep -r InstanceCard frontend/src`)

## 2. Tabela de instâncias

- [x] 2.1 Reescrever `frontend/src/features/instances/InstancesSection.jsx`
      para desenhar uma `Table` (colunas: Imagem, Referência, Estado, Ações)
      com uma `InstanceTableRow` por instância, no lugar do `Grid` de
      cartões; recebe `onOpenSession(instanceId)` como prop em vez de
      controlar abertura/fechamento internamente; verificar com teste
      atualizado em `InstancesSection.test.jsx` que a tabela lista todas as
      instâncias e que clicar em "Abrir sessão" chama `onOpenSession` com o
      id correto, sem nenhuma instância local de sessão aberta
- [x] 2.2 Remover o estado `openSessionIds` e a lógica de redimensionamento
      a 80% de `InstancesSection.jsx` (não se aplica mais a uma tabela);
      verificar que os testes antigos de "80% da tela"/"sessão ocupa a
      largura total do card" foram removidos ou substituídos pelos novos
      cenários de 2.1

## 3. Visão dedicada da sessão aberta

- [x] 3.1 Criar `frontend/src/features/instances/InstanceSessionView.jsx`:
      cabeçalho com nome do template, chip de estado e botão "Voltar"
      (`onBack`), área de sessão reaproveitando `InstanceSession.jsx` sem
      alterá-lo, com altura baseada em `calc(100vh - <cabeçalho>)` em vez da
      proporção 16:9; verificar com teste novo `InstanceSessionView.test.jsx`
      que a sessão é exibida quando a instância está em execução
- [x] 3.2 Adicionar os botões Parar e Excluir (com o mesmo diálogo de
      confirmação já usado em `InstanceTableRow`) ao cabeçalho de
      `InstanceSessionView`; verificar com teste que Parar chama `onStop` e
      mantém a visão aberta mostrando o aviso de parada no lugar do iframe, e
      que Excluir (confirmado) chama `onDelete` seguido de `onBack`
- [x] 3.3 Quando a instância da visão não estiver em execução (parada ou
      erro), exibir o mesmo aviso explicativo que a listagem já mostra
      ("Parada — por você ou por inatividade...", ou a mensagem de erro) no
      lugar do iframe; verificar com teste cobrindo os três estados
      (execução, parada, erro)

## 4. Troca de visão em HomePage

- [x] 4.1 Adicionar `openInstanceId` (estado local, `null` por padrão) a
      `frontend/src/pages/HomePage.jsx`: quando `null`, renderiza
      `CatalogSection` + `InstancesSection` (passando `onOpenSession` que
      seta `openInstanceId`); quando preenchido, renderiza
      `InstanceSessionView` para a instância correspondente em `instances`,
      com `onBack` que limpa `openInstanceId`; verificar com teste novo ou
      atualizado em `HomePage.test.jsx` (criar se não existir) cobrindo a
      troca de visão nos dois sentidos
- [x] 4.2 Se `openInstanceId` não corresponder a nenhuma instância em
      `instances` (ex.: excluída por outro caminho), voltar sozinho para a
      listagem sem exigir um clique em "Voltar"; verificar com teste
      cobrindo esse caso

## 5. Verificação integrada

- [x] 5.1 Rodar a suíte completa do frontend (`npm test`) e verificar que
      todos os testes passam
- [x] 5.2 Validar manualmente no preview: abrir uma sessão a partir da
      tabela, confirmar que a listagem some e a sessão ocupa a área central;
      parar pela visão da sessão e confirmar que ela permanece mostrando o
      aviso de parada; voltar à listagem; excluir uma instância a partir da
      visão da sessão e confirmar o retorno automático à listagem

## Workflow follow-up

- Sincronizar a spec delta (`desktop-instances`) para a spec principal e
  arquivar esta change após a revisão do usuário.
