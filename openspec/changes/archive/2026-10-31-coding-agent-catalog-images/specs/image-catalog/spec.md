# Spec Delta

## MODIFIED Requirements

### Requirement: Estado de prontidão da imagem é observável

Cada entrada DEVE expor seu estado entre provisionamento em andamento, pronta
e falha, e o progresso DEVE ser consultável enquanto o provisionamento ocorre,
seja ele por download de um repositório remoto ou por build local de um
Dockerfile.

#### Scenario: Consulta durante o download

- **WHEN** um administrador consulta uma entrada com download em andamento
- **THEN** o sistema retorna o estado de download e o progresso corrente

#### Scenario: Download concluído

- **WHEN** o download de uma imagem termina com sucesso
- **THEN** a entrada passa ao estado pronta

#### Scenario: Download falha

- **WHEN** o download de uma imagem falha
- **THEN** a entrada passa ao estado de falha
- **AND** o motivo da falha fica disponível ao administrador

#### Scenario: Consulta durante o build

- **WHEN** um administrador consulta uma entrada com build em andamento
- **THEN** o sistema retorna o estado de provisionamento e o progresso
  corrente

#### Scenario: Build concluído

- **WHEN** o build de uma imagem termina com sucesso
- **THEN** a entrada passa ao estado pronta

#### Scenario: Build falha

- **WHEN** o build de uma imagem falha
- **THEN** a entrada passa ao estado de falha
- **AND** o motivo da falha fica disponível ao administrador

## ADDED Requirements

### Requirement: Provisionamento por build é distinguível e repetível

Cada entrada DEVE registrar se foi provisionada por download de registry ou
por build local. Quando o provisionamento falhar, o sistema DEVE permitir
repeti-lo pelo mesmo tipo usado originalmente.

#### Scenario: Repetir download falho

- **GIVEN** uma entrada provisionada por download em estado de falha
- **WHEN** a repetição é solicitada
- **THEN** o sistema executa um novo download

#### Scenario: Repetir build falho

- **GIVEN** uma entrada provisionada por build em estado de falha
- **WHEN** a repetição é solicitada
- **THEN** o sistema executa um novo build, não um download

### Requirement: Rebuild só ocorre quando o contexto de build muda

Uma entrada provisionada por build DEVE guardar a identidade do conteúdo do
seu contexto e só DEVE ser reconstruída quando esse conteúdo mudar.

#### Scenario: Contexto inalterado

- **GIVEN** uma entrada provisionada por build já pronta
- **WHEN** o provisionamento é reavaliado sem mudança de contexto
- **THEN** a entrada não é reconstruída

#### Scenario: Contexto alterado

- **GIVEN** uma entrada provisionada por build já pronta
- **WHEN** o conteúdo do seu contexto de build muda
- **THEN** a entrada é reconstruída

### Requirement: Entrada do catálogo define a porta de encaminhamento do container

Cada entrada DEVE registrar a porta em que o processo de interface do
container escuta, com um valor padrão quando omitida. A porta DEVE ser usada
tanto pelo encaminhamento de sessão quanto pela variável de ambiente `PORT`
injetada no container.

#### Scenario: Porta definida no provisionamento interno

- **WHEN** o portal provisiona uma entrada com porta de encaminhamento própria
- **THEN** a entrada guarda essa porta
- **AND** instâncias criadas a partir dela são encaminhadas a essa porta
- **AND** o container recebe essa porta como `PORT`

#### Scenario: Porta omitida no registro

- **WHEN** uma entrada é registrada sem informar a porta de encaminhamento
- **THEN** a entrada recebe a porta padrão do sistema
