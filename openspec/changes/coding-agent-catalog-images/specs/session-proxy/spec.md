# Spec Delta

## ADDED Requirements

### Requirement: Encaminhamento direciona à porta definida pela entrada do catálogo

O sistema DEVE encaminhar a requisição e o canal persistente de uma instância
à porta de encaminhamento registrada na entrada do catálogo da sua imagem, em
vez de uma porta fixa única para todas as imagens.

#### Scenario: Imagem com porta própria

- **GIVEN** uma instância cuja imagem registra uma porta de encaminhamento
  diferente da porta padrão
- **WHEN** uma requisição é encaminhada a essa instância
- **THEN** o sistema a encaminha à porta registrada na imagem

#### Scenario: Imagem com porta padrão

- **GIVEN** uma instância cuja imagem não define uma porta de encaminhamento
  diferente da padrão
- **WHEN** uma requisição é encaminhada a essa instância
- **THEN** o sistema a encaminha à porta padrão, como hoje
