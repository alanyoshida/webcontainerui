# user-management Specification

## Purpose

Administra as contas que podem usar o portal e os grupos que organizam essas
contas, de modo que o administrador controle quem existe no sistema e a quais
grupos cada pessoa pertence — a base sobre a qual as permissões de imagem são
resolvidas.

## Requirements

### Requirement: Somente administrador cria contas

O sistema NÃO DEVE oferecer auto-cadastro. A criação de contas DEVE estar
disponível apenas a usuários com papel de administrador.

#### Scenario: Usuário comum tenta criar conta

- **WHEN** um usuário autenticado sem papel de administrador tenta criar uma conta
- **THEN** o sistema recusa a operação por falta de permissão
- **AND** nenhuma conta é criada

#### Scenario: Administrador cria conta

- **WHEN** um administrador envia e-mail, senha inicial e grupos de um novo usuário
- **THEN** o sistema cria a conta ativa com esses grupos
- **AND** o novo usuário consegue autenticar com a senha inicial

### Requirement: Identificador de usuário é único

O sistema DEVE recusar a criação de uma conta cujo identificador já pertença a
outra conta, inclusive a uma conta desabilitada.

#### Scenario: E-mail já em uso

- **WHEN** um administrador tenta criar conta com e-mail que já existe
- **THEN** o sistema recusa a operação e informa o conflito
- **AND** a conta existente permanece inalterada

### Requirement: Primeiro administrador criado na inicialização

O sistema DEVE provisionar uma conta de administrador na primeira inicialização a
partir de configuração do ambiente, para que exista um caminho de entrada sem
auto-cadastro.

#### Scenario: Primeira inicialização com banco vazio

- **GIVEN** um banco sem nenhum usuário
- **WHEN** o sistema inicia com as credenciais de administrador configuradas
- **THEN** uma conta de administrador ativa passa a existir

#### Scenario: Inicialização subsequente

- **GIVEN** um banco que já contém usuários
- **WHEN** o sistema inicia novamente com as mesmas credenciais configuradas
- **THEN** nenhuma conta é criada ou sobrescrita

### Requirement: Administrador desabilita conta sem apagá-la

O sistema DEVE permitir desabilitar uma conta, bloqueando seu acesso e
preservando seu registro e seus dados associados.

#### Scenario: Conta desabilitada

- **WHEN** um administrador desabilita uma conta
- **THEN** a conta passa a constar como desabilitada
- **AND** o registro do usuário e seus volumes continuam existindo

### Requirement: Administrador gerencia grupos

O sistema DEVE permitir ao administrador criar grupos, renomeá-los e removê-los,
sendo o nome do grupo único.

#### Scenario: Criação de grupo

- **WHEN** um administrador cria um grupo com nome ainda não usado
- **THEN** o grupo passa a existir e pode receber membros e permissões

#### Scenario: Nome de grupo duplicado

- **WHEN** um administrador tenta criar um grupo com nome já existente
- **THEN** o sistema recusa a operação e informa o conflito

### Requirement: Administrador gerencia associação de usuários a grupos

O sistema DEVE permitir ao administrador incluir e remover um usuário de um grupo,
podendo um usuário pertencer a vários grupos ao mesmo tempo.

#### Scenario: Usuário em múltiplos grupos

- **WHEN** um administrador associa um usuário a dois grupos distintos
- **THEN** o usuário consta como membro de ambos

#### Scenario: Remoção de membro

- **WHEN** um administrador remove um usuário de um grupo
- **THEN** o usuário deixa de constar como membro daquele grupo
- **AND** sua associação aos demais grupos é preservada

### Requirement: Usuário sem grupo não tem acesso a imagem alguma

Um usuário que não pertença a nenhum grupo com permissão DEVE conseguir
autenticar e DEVE ver um catálogo vazio, sem poder criar instância.

#### Scenario: Conta recém-criada sem grupos

- **WHEN** um usuário sem nenhum grupo autentica e consulta o catálogo
- **THEN** o catálogo retorna vazio
- **AND** qualquer tentativa de criar instância é recusada por falta de permissão

### Requirement: Remoção de grupo não remove seus usuários

Ao remover um grupo, o sistema DEVE preservar as contas que eram seus membros e
DEVE apenas descartar as permissões que o grupo concedia.

#### Scenario: Grupo removido

- **GIVEN** um grupo com membros e com permissão sobre uma imagem
- **WHEN** o administrador remove o grupo
- **THEN** as contas dos membros continuam existindo e ativas
- **AND** aquela permissão deixa de valer para esses usuários
