# Spec Delta

## Purpose

Define qual banco de dados o portal usa em cada ambiente, como a escolha é
configurada por variáveis de ambiente e como a composição de produção provê
o PostgreSQL — mantendo o desenvolvimento local sem dependências externas.

## ADDED Requirements

### Requirement: Seleção do banco por ambiente

O portal DEVE usar SQLite (caminho `WCUI_DB_PATH`) quando
`WCUI_DATABASE_URL` não estiver definida, e DEVE usar o PostgreSQL
apontado por `WCUI_DATABASE_URL` quando a variável estiver definida. A
escolha NÃO DEVE exigir nenhuma outra configuração nem mudança de código.

#### Scenario: Desenvolvimento local sem variável extra

- **WHEN** o portal sobe sem `WCUI_DATABASE_URL` definida
- **THEN** ele persiste todos os dados no SQLite do caminho `WCUI_DB_PATH`

#### Scenario: Produção apontando para o Postgres

- **WHEN** o portal sobe com `WCUI_DATABASE_URL` definida para uma
  conexão PostgreSQL válida
- **THEN** ele persiste todos os dados nesse PostgreSQL e não cria nem
  usa o arquivo SQLite

### Requirement: Provisão de schema idempotente nos dois motores

Ao iniciar com qualquer um dos dois motores, o portal DEVE criar o schema
completo em banco vazio e DEVE aplicar as migrações idempotentes em banco
pré-existente, sem erro e sem duplicar estruturas, de modo que reiniciar
sobre um banco já migrado seja uma operação nula.

#### Scenario: Primeiro boot em banco vazio

- **WHEN** o portal inicia contra um banco PostgreSQL recém-criado e vazio
- **THEN** todas as tabelas, índices e vínculos do schema são criados e o
  portal fica operacional

#### Scenario: Boot repetido sobre banco já migrado

- **WHEN** o portal reinicia contra um banco já migrado por uma execução
  anterior
- **THEN** o bootstrap conclui sem erro e os dados anteriores permanecem
  intactos

### Requirement: Serviço PostgreSQL na composição de produção

A composição de produção DEVE incluir um serviço PostgreSQL na rede
interna, com volume próprio persistente, credencial fornecida por
variável de ambiente e verificação de prontidão; o portal DEVE iniciar
somente após o banco estar pronto. O serviço de banco NÃO DEVE publicar
porta no host.

#### Scenario: Subida da composição de produção

- **WHEN** o operador executa `docker compose up` com as variáveis de
  produção definidas
- **THEN** o serviço de banco inicia com sua credencial configurada e o
  portal só fica pronto depois de o banco responder como saudável

#### Scenario: Banco inacessível não derruba a subida em loop silencioso

- **WHEN** o PostgreSQL falha a verificação de prontidão na subida
- **THEN** o portal não recebe tráfego como saudável até o banco ficar
  pronto

### Requirement: Persistência entre recriações dos containers

Os dados gravados no PostgreSQL de produção DEVEM sobreviver à recriação
dos containers da composição, via volume nomeado.

#### Scenario: Derrubar e subir novamente

- **WHEN** o operador executa `docker compose down` seguido de `up` na
  composição de produção, sem apagar volumes
- **THEN** usuários, sessões, catálogo e instâncias registrados antes do
  `down` continuam acessíveis após a subida

### Requirement: Comportamento da aplicação independe do motor

Todas as operações do portal — autenticação, catálogo, instâncias,
identidade SSH, documentos, skills, servidores MCP e métricas — DEVEM
se comportar de forma equivalente nos dois motores, incluindo
timestamps, valores booleanos e os segredos cifrados em repouso.

#### Scenario: Fluxo de login e criação de usuário no Postgres

- **WHEN** um administrador cria um usuário e esse usuário faz login com
  o portal conectado ao PostgreSQL
- **THEN** o fluxo ocorre como no SQLite, com as mesmas respostas de
  sucesso e de erro

#### Scenario: Métricas de uso com timestamps do Postgres

- **WHEN** uma instância é iniciada e parada com o portal no PostgreSQL
- **THEN** o ciclo de execução é registrado com início e fim consultáveis
  pelas métricas administrativas, sem ambiguidade de fuso
