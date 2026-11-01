# Spec Delta

## MODIFIED Requirements

### Requirement: Administrador desabilita conta sem apagá-la

O sistema DEVE permitir desabilitar uma conta, bloqueando seu acesso e
preservando seu registro e seus dados associados. A desabilitação DEVE exigir
confirmação explícita com o nome da conta afetada, e o sistema NÃO DEVE
permitir que um administrador desabilite a própria conta.

#### Scenario: Conta desabilitada

- **WHEN** um administrador desabilita uma conta
- **THEN** a conta passa a constar como desabilitada
- **AND** o registro do usuário e seus volumes continuam existindo

#### Scenario: Desabilitação exige confirmação

- **WHEN** a desabilitação de uma conta é pedida sem confirmação explícita
- **THEN** o sistema não altera a conta

#### Scenario: Auto-desabilitação é recusada

- **WHEN** um administrador tenta desabilitar a própria conta
- **THEN** o sistema recusa a operação e informa o motivo
- **AND** a conta permanece ativa
