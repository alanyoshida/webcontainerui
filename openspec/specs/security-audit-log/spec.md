# security-audit-log Specification

## Purpose

Trilha estruturada e consultável dos eventos de segurança do portal: quem fez o quê, de onde e com que desfecho — sem jamais registrar segredos.

## Requirements

### Requirement: Eventos de segurança são registrados em trilha estruturada

O sistema DEVE emitir, para cada evento de segurança relevante, um registro estruturado contendo o nome do evento, o ator (identificador e e-mail, quando houver), a origem (IP do cliente, quando disponível), o alvo da ação e o desfecho, em formato de máquina consultável pelo operador do serviço.

#### Scenario: Tentativa de login com falha

- **WHEN** uma tentativa de login com credenciais inválidas é processada
- **THEN** um registro de evento de falha de autenticação é emitido com o identificador tentado, a origem e o desfecho

#### Scenario: Operação administrativa

- **WHEN** um administrador altera gestão de acesso (usuário, grupo ou permissão de imagem) ou uma biblioteca que propaga aos containers (documento, servidor MCP, skill, imagem do catálogo)
- **THEN** um registro do evento correspondente é emitido com o administrador como ator e o objeto alterado como alvo

#### Scenario: Ciclo de vida de instância

- **WHEN** uma instância é criada, parada ou excluída pelo dono, ou falha ao provisionar
- **THEN** um registro do evento correspondente é emitido com o dono como ator e a instância como alvo

### Requirement: A trilha cobre a recusa pelo limitador de login

O sistema DEVE emitir registro próprio quando uma tentativa de login é recusada pela limitação de tentativas, distinto da falha de credencial.

#### Scenario: Login recusado pelo limitador

- **WHEN** uma tentativa de login é recusada por excesso de falhas
- **THEN** um registro de evento de recusa é emitido com o identificador tentado e a origem, sem verificação de credencial

### Requirement: Segredos nunca aparecem na trilha

O sistema NÃO DEVE registrar, em nenhum evento, valores de senha, token de sessão, credencial interna de instância, chave SSH privada ou valores de variáveis de ambiente/headers de servidor MCP.

#### Scenario: Evento de login sem segredo

- **WHEN** qualquer evento de autenticação é emitido
- **THEN** o registro contém identificador e desfecho, mas nenhum valor de senha ou token apresentado na tentativa
