# auth Specification

## Purpose

Autentica pessoas no portal e governa o ciclo de vida da sessão, de modo que toda
requisição subsequente possa ser atribuída a um usuário conhecido e uma sessão
possa ser revogada a qualquer momento pelo próprio usuário ou pelo administrador.

## Requirements

### Requirement: Login com credenciais válidas emite sessão

O sistema DEVE emitir uma sessão autenticada quando receber o identificador e a
senha corretos de um usuário ativo.

#### Scenario: Credenciais corretas de usuário ativo

- **WHEN** um usuário ativo envia seu e-mail e senha corretos
- **THEN** o sistema cria uma sessão com prazo de expiração
- **AND** devolve o token da sessão num cookie
- **AND** as requisições seguintes com esse cookie são atribuídas a esse usuário

### Requirement: Falha de autenticação não revela existência da conta

O sistema DEVE responder de forma indistinguível a um identificador inexistente e
a uma senha incorreta, para não permitir enumeração de contas.

#### Scenario: Identificador inexistente

- **WHEN** alguém envia um e-mail que não existe com qualquer senha
- **THEN** o sistema responde com erro de credencial inválida
- **AND** a mensagem e o código de status são idênticos ao caso de senha errada

#### Scenario: Senha incorreta de usuário existente

- **WHEN** um usuário existente envia a senha errada
- **THEN** o sistema responde com erro de credencial inválida
- **AND** nenhuma sessão é criada

### Requirement: Senha armazenada apenas como hash

O sistema DEVE armazenar senhas somente como hash produzido por função de
derivação resistente a força bruta, e NUNCA em texto plano ou de forma
reversível.

#### Scenario: Inspeção do registro do usuário

- **WHEN** o registro de um usuário é lido do banco de dados
- **THEN** o campo de senha contém um hash com sal
- **AND** a senha original não pode ser recuperada a partir do registro

### Requirement: Sessão expirada é rejeitada

O sistema DEVE recusar qualquer sessão cujo prazo de expiração já passou,
tratando a requisição como não autenticada.

#### Scenario: Requisição com sessão vencida

- **WHEN** uma requisição apresenta cookie de sessão cuja expiração já passou
- **THEN** o sistema responde como não autenticado
- **AND** não executa a ação pedida

### Requirement: Logout revoga a sessão imediatamente

O sistema DEVE invalidar a sessão corrente no logout, de modo que o mesmo token
não possa mais autenticar requisições.

#### Scenario: Reuso de token após logout

- **WHEN** um usuário faz logout e em seguida reapresenta o mesmo token
- **THEN** o sistema responde como não autenticado

### Requirement: Usuário desabilitado não autentica

O sistema DEVE recusar o login de um usuário desabilitado e DEVE revogar as
sessões já existentes dele no momento da desabilitação.

#### Scenario: Login de conta desabilitada

- **WHEN** um usuário desabilitado envia a senha correta
- **THEN** o sistema recusa o login
- **AND** nenhuma sessão é criada

#### Scenario: Sessão ativa no momento da desabilitação

- **GIVEN** um usuário com sessão válida em uso
- **WHEN** o administrador desabilita essa conta
- **THEN** as sessões existentes desse usuário passam a ser recusadas

### Requirement: Cookie de sessão protegido no transporte

O cookie de sessão DEVE ser marcado como `HttpOnly` e `SameSite`, e DEVE ser
marcado como `Secure` quando o portal for servido sobre HTTPS, para não ficar
legível a scripts nem ser enviado em requisições de terceiros.

#### Scenario: Atributos do cookie emitido

- **WHEN** o sistema emite o cookie de sessão sobre HTTPS
- **THEN** o cookie carrega os atributos `HttpOnly`, `Secure` e `SameSite`

### Requirement: Identidade do usuário exigida fora das rotas públicas

O sistema DEVE recusar qualquer requisição sem sessão válida a rotas que não sejam
explicitamente públicas, incluindo a API, o painel administrativo e o acesso às
instâncias.

#### Scenario: Requisição anônima a rota protegida

- **WHEN** uma requisição sem cookie de sessão atinge uma rota protegida
- **THEN** o sistema responde como não autenticado
- **AND** não revela se o recurso pedido existe
