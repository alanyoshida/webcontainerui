# Spec Delta

## ADDED Requirements

### Requirement: Imagens de agente recebem capa padrão com o logo da ferramenta

Cada entrada de imagem de agente DEVE receber, no startup, uma capa padrão que
usa o logo da ferramenta correspondente, sem exigir upload do administrador.
Quando houver uma capa enviada pelo administrador, ela prevalece.

#### Scenario: Primeira inicialização das imagens de agente

- **GIVEN** as imagens de agente são provisionadas sem capa do administrador
- **WHEN** o portal inicia
- **THEN** cada entrada de agente recebe uma capa padrão com o logo da sua
  ferramenta

#### Scenario: Administrador envia capa própria

- **GIVEN** uma entrada de agente com capa enviada pelo administrador
- **WHEN** o portal inicia
- **THEN** a capa do administrador continua sendo exibida

#### Scenario: Logo versionado do agente muda

- **GIVEN** uma entrada de agente que ainda usa a capa padrão
- **AND** o arquivo versionado do logo dessa ferramenta mudou
- **WHEN** o portal inicia
- **THEN** a entrada passa a usar a nova capa padrão
