# Spec Delta

## MODIFIED Requirements

### Requirement: Vincular ou desvincular skill dispara rebuild imediato da imagem

Ao vincular ou desvincular uma skill de uma imagem de agente, o sistema DEVE
exigir confirmação explícita do administrador, informando que a operação
dispara um novo build da imagem. Após a confirmação, o sistema DEVE disparar
imediatamente o novo build em segundo plano, sem bloquear a resposta ao
administrador, com o progresso consultável como em qualquer outro build.

#### Scenario: Vínculo exige confirmação

- **WHEN** um administrador aciona o vínculo de uma skill a uma imagem
- **THEN** o build só é disparado após a confirmação explícita, que informa
  o custo do rebuild

#### Scenario: Vínculo dispara rebuild

- **GIVEN** uma imagem de agente já pronta
- **WHEN** um administrador confirma o vínculo de uma skill a essa imagem
- **THEN** o sistema responde imediatamente
- **AND** a entrada passa ao estado de build em andamento
- **AND**, ao concluir, a imagem resultante tem a skill instalada

#### Scenario: Desvínculo dispara rebuild

- **GIVEN** uma imagem de agente pronta com uma skill vinculada
- **WHEN** um administrador confirma o desvínculo dessa skill da imagem
- **THEN** o sistema dispara um novo build da imagem
- **AND**, ao concluir, a imagem resultante não tem mais a skill instalada
