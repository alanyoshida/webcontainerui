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

#### Scenario: Conta desabilitada é indistinguível também por tempo

- **WHEN** alguém envia credenciais de uma conta desabilitada
- **THEN** o custo de verificação de senha é o mesmo dos demais casos de falha
- **AND** o tempo de resposta não permite distinguir conta desabilitada de conta inexistente ou de senha errada

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

#### Scenario: Portal servido atrás de proxy TLS confiável

- **GIVEN** o portal alcançado por um proxy confiável que termina TLS e informa o esquema original da requisição
- **WHEN** o login acontece por esse proxy com o cliente usando HTTPS
- **THEN** o cookie de sessão é emitido com o atributo `Secure`

#### Scenario: Portal sem proxy confiável configurado

- **GIVEN** o portal sem proxy confiável configurado
- **WHEN** uma requisição anuncia esquema HTTPS por cabeçalho encaminhado de origem não confiável
- **THEN** o portal não altera seu entendimento do esquema da requisição

### Requirement: Identidade do usuário exigida fora das rotas públicas

O sistema DEVE recusar qualquer requisição sem sessão válida a rotas que não sejam
explicitamente públicas, incluindo a API, o painel administrativo e o acesso às
instâncias.

#### Scenario: Requisição anônima a rota protegida

- **WHEN** uma requisição sem cookie de sessão atinge uma rota protegida
- **THEN** o sistema responde como não autenticado
- **AND** não revela se o recurso pedido existe

### Requirement: Tentativas de login com falha são limitadas

O sistema DEVE limitar a taxa de tentativas de login com falha, por conta e por
origem do cliente, recusando temporariamente novas tentativas quando um limiar
configurável for excedido em uma janela de tempo, sem bloqueio permanente.

#### Scenario: Excesso de falhas para a mesma conta

- **GIVEN** mais tentativas com falha para um e-mail do que o limiar configurado, dentro da janela
- **WHEN** uma nova tentativa de login chega para esse e-mail
- **THEN** o sistema responde com erro de taxa excedida, sem verificar a senha
- **AND** a resposta indica quanto tempo esperar antes da próxima tentativa

#### Scenario: Recusa expirada permite login correto

- **GIVEN** uma conta sob recusa temporária por excesso de falhas
- **WHEN** o período de recusa passa
- **THEN** o login com as credenciais corretas volta a ser aceito normalmente

#### Scenario: Limite por conta não revela existência da conta

- **WHEN** tentativas com falha excedem o limiar para um e-mail que não corresponde a nenhuma conta
- **THEN** o sistema responde com o mesmo erro de taxa excedida dado a uma conta existente
- **AND** o corpo da resposta não distingue os dois casos

#### Scenario: Limite por origem alcança várias contas

- **GIVEN** tentativas com falha vindas da mesma origem do cliente, ainda que para e-mails distintos
- **WHEN** o total excede o limiar por origem
- **THEN** o sistema recusa temporariamente novas tentativas dessa origem

#### Scenario: Login válido dentro do limite não é afetado

- **WHEN** um usuário faz login com credenciais corretas sem ter excedido nenhum limiar
- **THEN** a sessão é emitida normalmente

### Requirement: Sessões expiradas ou revogadas são purgadas

O sistema DEVE remover periodicamente do armazenamento as sessões expiradas ou revogadas há mais que um período de carência configurável, mantendo a tabela de sessões limitada ao uso recente.

#### Scenario: Sessão expirada além da carência é removida

- **GIVEN** uma sessão cuja expiração passou há mais que o período de carência
- **WHEN** a purga periódica executa
- **THEN** o registro da sessão é removido do armazenamento

#### Scenario: Sessão revogada recentemente é preservada

- **GIVEN** uma sessão revogada há menos que o período de carência
- **WHEN** a purga periódica executa
- **THEN** o registro da sessão permanece no armazenamento

#### Scenario: Sessão ativa nunca é removida

- **GIVEN** uma sessão válida e não expirada
- **WHEN** a purga periódica executa
- **THEN** o registro da sessão permanece e continua autenticando requisições
