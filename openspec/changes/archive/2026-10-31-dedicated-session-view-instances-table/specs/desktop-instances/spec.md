# Spec Delta

## REMOVED Requirements

### Requirement: Listagem de instâncias adapta o layout ao tamanho da tela

**Reason**: A listagem deixou de ser uma grade de cartões; passa a ser uma
tabela com uma linha por instância e ações alinhadas à linha, substituindo o
modelo de colunas responsivas.
**Migration**: Nenhuma ação necessária do usuário. O requisito substituto é
"Listagem de instâncias é apresentada em tabela com ações por linha".

### Requirement: Sessão embutida permanece utilizável em qualquer largura de coluna

**Reason**: A sessão deixou de ser embutida dentro do cartão da instância na
listagem. Abrir uma sessão agora troca para uma visão dedicada que ocupa a
área central da página, fora do contexto de grade/colunas.
**Migration**: Nenhuma ação necessária do usuário. O requisito substituto é
"Abrir sessão troca a página para uma visão dedicada".

## ADDED Requirements

### Requirement: Listagem de instâncias é apresentada em tabela com ações por linha

A listagem de instâncias do usuário DEVE apresentar uma linha por instância,
com nome do template, referência da imagem, estado e as ações disponíveis
alinhadas na mesma linha, em vez de cartões em grade.

#### Scenario: Ações de uma instância em execução

- **WHEN** um usuário consulta a listagem e uma de suas instâncias está em execução
- **THEN** a linha dessa instância oferece as ações abrir sessão, parar e excluir

#### Scenario: Ações de uma instância parada ou em erro

- **WHEN** um usuário consulta a listagem e uma de suas instâncias está parada ou em erro
- **THEN** a linha dessa instância oferece as ações iniciar e excluir

### Requirement: Abrir sessão troca a página para uma visão dedicada

Ao abrir a sessão de uma instância, o sistema DEVE substituir a listagem pela
visão dessa sessão como conteúdo central da página, sem navegar para outro
endereço. O usuário DEVE poder voltar à listagem a partir da visão da sessão.

#### Scenario: Abertura de sessão

- **WHEN** um usuário abre a sessão de uma instância em execução
- **THEN** a listagem deixa de ser exibida
- **AND** a sessão passa a ocupar a área central da página

#### Scenario: Retorno à listagem

- **GIVEN** a visão dedicada de uma sessão aberta
- **WHEN** o usuário aciona a ação de voltar
- **THEN** a listagem volta a ser exibida no lugar da visão da sessão

### Requirement: Visão da sessão aberta oferece parar e excluir

A visão dedicada de uma sessão aberta DEVE oferecer as mesmas ações de parar
e excluir disponíveis na listagem, sem exigir que o usuário volte à listagem
para executá-las.

#### Scenario: Parar pela visão da sessão

- **GIVEN** a visão dedicada de uma sessão aberta
- **WHEN** o usuário aciona a ação de parar
- **THEN** a instância passa a parada
- **AND** o usuário permanece na visão dedicada, que passa a refletir o
  estado parado em vez da sessão incorporada

#### Scenario: Excluir pela visão da sessão

- **GIVEN** a visão dedicada de uma sessão aberta
- **WHEN** o usuário confirma a exclusão da instância
- **THEN** a instância e seu volume são removidos
- **AND** o usuário retorna à listagem
