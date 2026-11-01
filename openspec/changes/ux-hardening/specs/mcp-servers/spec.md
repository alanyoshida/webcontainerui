# Spec Delta

## MODIFIED Requirements

### Requirement: Remoção de servidor MCP da biblioteca desvincula automaticamente, sem rebuild

O sistema DEVE permitir remover um servidor MCP da biblioteca mesmo vinculado
a uma ou mais imagens, removendo o vínculo de todas elas e atualizando as
instâncias vivas afetadas na mesma operação. A remoção DEVE exigir confirmação
explícita que informe que o efeito alcança imediatamente as instâncias em
execução das imagens vinculadas.

#### Scenario: Remoção exige confirmação de efeito imediato

- **WHEN** um administrador aciona a remoção de um servidor MCP vinculado a
  imagens com instâncias vivas
- **THEN** a remoção só acontece após confirmação explícita que informa o
  efeito imediato nessas instâncias

#### Scenario: Remover servidor MCP vinculado

- **GIVEN** um servidor MCP vinculado a uma ou mais imagens de agente,
  com instâncias vivas
- **WHEN** um administrador remove esse servidor da biblioteca
- **THEN** o servidor deixa de existir na biblioteca
- **AND** todas as imagens que o referenciavam deixam de referenciá-lo
- **AND** as instâncias vivas afetadas deixam de ter esse servidor
  configurado
