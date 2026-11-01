# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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
