# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
